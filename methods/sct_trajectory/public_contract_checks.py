"""生成/修复阶段的公开契约静态检查，不执行候选代码，不计作 Function/Secure。

只从调用方提供的公开字段提取高置信规则：入口、可识别的签名，以及明确要求
保留的外部绑定。不会读取 setup、测试、参考答案、经验库或任何文件，也不会修改
代码/长期经验。PLT 与 Base/Plus 均只得到同一套公开规则；未识别的语义保持未测量。
检查发现的是源码中的潜在重绑定路径，不声称该路径已在正式测试中执行。
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import re
from dataclasses import dataclass


_REQUIREMENTS_VERSION = 'public_contract_requirements.v1'
_RESULT_VERSION = 'public_contract_checks.v1'
_PUBLIC_FIELDS = ('language', 'entry_point', 'function_name', 'description', 'context',
                  'arguments', 'signature', 'function_signature')
_IDENTIFIER = r'[A-Za-z_]\w*'
_ENTRY_FIELDS = ('entry_point', 'function_name')
_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _public_fields(task: dict) -> dict:
    """读取公开字段白名单；允许原始记录的 task_description，不递归查看其他字段。"""
    description = task.get('task_description')
    source = description if isinstance(description, dict) else task
    fields = {key: source[key] for key in _PUBLIC_FIELDS if isinstance(source.get(key), str)}
    if 'language' not in fields and isinstance(task.get('language'), str):
        fields['language'] = task['language']
    return fields


def _signature_spec(node, *, mode: str, source: str) -> dict:
    """把公开 Python 骨架变成不执行表达式的签名证据；不以类型注解推断语义。"""
    args = node.args
    positional = list(args.posonlyargs) + list(args.args)
    first_default = len(positional) - len(args.defaults)
    parameters = []
    for index, argument in enumerate(positional):
        default = args.defaults[index - first_default] if index >= first_default else None
        parameters.append({
            'name': argument.arg,
            'kind': 'POSITIONAL_ONLY' if index < len(args.posonlyargs) else 'POSITIONAL_OR_KEYWORD',
            'required': default is None,
            'default_ast': ast.dump(default, include_attributes=False) if default is not None else None,
        })
    if args.vararg:
        parameters.append({'name': args.vararg.arg, 'kind': 'VAR_POSITIONAL', 'required': False, 'default_ast': None})
    for argument, default in zip(args.kwonlyargs, args.kw_defaults):
        parameters.append({'name': argument.arg, 'kind': 'KEYWORD_ONLY', 'required': default is None,
                           'default_ast': ast.dump(default, include_attributes=False) if default is not None else None})
    if args.kwarg:
        parameters.append({'name': args.kwarg.arg, 'kind': 'VAR_KEYWORD', 'required': False, 'default_ast': None})
    return {'mode': mode, 'parameters': parameters, 'async': isinstance(node, ast.AsyncFunctionDef),
            'public_source': source}


def _extract_signature(fields: dict, entry_point: str) -> dict | None:
    """只解析完整公开骨架/签名或完全可识别的参数列表；歧义、可选 prose 不猜测。"""
    if not entry_point:
        return None
    for field in ('function_signature', 'signature', 'description'):
        text = fields.get(field, '').strip()
        if not text:
            continue
        candidates = [text]
        candidates.extend(re.findall(r'```(?:python|py)?\s*\n(.*?)```', text, re.DOTALL))
        if field != 'description':
            header = text if re.match(r'(?:async\s+)?def\s+', text) else 'def ' + text
            candidates.append(header.rstrip(':') + ':\n    pass\n')
        for candidate in candidates:
            try:
                tree = ast.parse(candidate)
            except (SyntaxError, ValueError):
                continue
            matching = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and node.name == entry_point]
            if len(matching) == 1:
                return _signature_spec(matching[0], mode='python_signature', source=field)

    arguments = fields.get('arguments', '').strip()
    if not arguments or re.search(r'\b(optional|defaults?|omitted|variadic)\b', arguments, re.IGNORECASE):
        return None
    names = []
    for line in arguments.splitlines():
        line = re.sub(r'^\s*[-*]\s*', '', line.strip())
        if not line:
            continue
        match = re.match(rf'^`?({_IDENTIFIER})`?\s*:', line)
        if not match:
            match = re.match(rf'^[A-Za-z_][\w.\[\], ()]*,\s*`?({_IDENTIFIER})`?\s*:', line)
        if not match or match.group(1) in names:
            return None
        names.append(match.group(1))
    if not names:
        return None
    # 自然语言列表不明确 positional-only/keyword-only/default；只检查列明的名字与位置。
    return {'mode': 'documented_arguments', 'names': names, 'public_source': 'arguments'}


def _protected_bindings(fields: dict) -> list[dict]:
    """提取显式 supplied/unchanged 或 pre-existing 绑定；仅 global 不构成禁止初始化。"""
    protected = {}
    for field in ('context', 'description'):
        text = fields.get(field, '')
        if not text:
            continue
        declarations = {match.group(1) for match in re.finditer(rf'(?m)^\s*[-*]?\s*`?({_IDENTIFIER})`?\s*:', text)}
        quoted = {match.group(1) for match in re.finditer(rf"[`']({_IDENTIFIER})[`']", text)}

        def add(name: str, evidence: str, reason: str) -> None:
            if not name.isidentifier() or name in protected:
                return
            protected[name] = {'name': name, 'reason': reason,
                               'public_source': field, 'evidence': evidence.strip()[:500]}

        explicit = [
            rf'\b(?:use|keep|preserve)\s+(?:the\s+)?(?:supplied|provided|existing)\s+[`\']?({_IDENTIFIER})[`\']?\s+unchanged\b',
            rf'\bdo\s+not\s+(?:redefine|reassign|rebind|replace|overwrite)\s+(?:the\s+)?[`\']?({_IDENTIFIER})[`\']?\b',
        ]
        for pattern in explicit:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                name = match.group(1)
                prefix = re.split(r'[.\n]', text[:match.start()])[-1]
                if re.search(r'\b(if|unless|may|might|optional)\b', prefix, re.IGNORECASE):
                    continue
                if name in declarations or name in quoted or name.isupper():
                    add(name, match.group(0), 'explicit_preserve_binding')
        for line in text.splitlines():
            match = re.match(rf'^\s*[-*]?\s*`?({_IDENTIFIER})`?\s*:\s*(.*)$', line)
            if (match and not re.search(r'\b(if|unless|may|might|optional)\b', match.group(2), re.IGNORECASE)
                    and re.search(r'\b(?:pre-existing|externally\s+(?:supplied|provided)|already\s+provided)\b', match.group(2), re.IGNORECASE)):
                add(match.group(1), line, 'explicit_external_binding')
        # 引号中的名称必须紧跟明确的 provided 语义；不把模板示例/普通全局变量猜作外部绑定。
        for sentence in re.split(r'[.\n]', text):
            if re.search(r'\b(?:you\s+are\s+provided\s+with|externally\s+supplied)\b', sentence, re.IGNORECASE):
                for match in re.finditer(rf"[`']({_IDENTIFIER})[`']\s+(?:dictionary|list|queue|template|object|mapping)\b", sentence, re.IGNORECASE):
                    add(match.group(1), sentence, 'explicit_external_binding')
    return [protected[name] for name in sorted(protected)]


def compile_public_contract(task: dict) -> dict:
    """生成前：公开任务→冻结静态规则；输入不含可用规则时记录未知，不访问测试或写库。"""
    fields = _public_fields(task)
    entries = {fields[key].strip() for key in _ENTRY_FIELDS if fields.get(key, '').strip()}
    entry_point = next(iter(entries)) if len(entries) == 1 else ''
    unknown = ['functional_behavior', 'security_behavior', 'card_implementation_semantics']
    if not entry_point.isidentifier():
        entry_point = ''
        unknown.append('entry_point_not_unambiguous')
    signature = _extract_signature(fields, entry_point)
    if signature is None:
        unknown.append('signature_not_unambiguous')
    result = {
        'schema_version': _REQUIREMENTS_VERSION,
        'source': 'public_task_fields_only',
        'language': fields.get('language', 'python').lower(),
        'entry_point': entry_point,
        'signature': signature,
        'protected_bindings': _protected_bindings(fields),
        'unmeasured': unknown,
    }
    return result


def _declarations(body: list[ast.AST]) -> set[str]:
    """取得当前词法作用域的 global 声明；不把嵌套函数/类的声明泄漏到外层。"""
    names = set()
    stack = list(body)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Global):
            names.update(node.names)
        elif not isinstance(node, _SCOPE_NODES):
            stack.extend(ast.iter_child_nodes(node))
    return names


@dataclass
class _Scope:
    kind: str
    globals: set[str]


class _BindingVisitor(ast.NodeVisitor):
    """检查源码绑定而非字符串匹配；局部变量、类属性、推导式变量不误当全局覆盖。"""

    def __init__(self, protected: set[str], tree: ast.Module):
        self.protected = protected
        self.scopes = [_Scope('module', set())]
        self.writes: list[dict] = []
        self.module_bindings: set[str] = set()
        self.module_binding_counts: dict[str, int] = {}
        self.callables: dict[str, list] = {}
        self.dynamic_binding = False
        # 一旦候选代码可能遮蔽 globals，就不根据 globals() 缺失检查裁剪分支。
        self.globals_shadowed = any(
            (isinstance(node, ast.Name) and node.id == 'globals' and isinstance(node.ctx, ast.Store))
            or (isinstance(node, ast.arg) and node.arg == 'globals')
            or (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == 'globals')
            or (isinstance(node, ast.alias) and (node.asname or node.name.split('.')[0]) == 'globals')
            for node in ast.walk(tree)
        )

    def _is_global(self, name: str, *, walrus: bool = False) -> bool:
        scopes = [scope for scope in self.scopes if scope.kind != 'comprehension'] if walrus else self.scopes
        scope = scopes[-1]
        return scope.kind == 'module' or name in scope.globals

    def _bind(self, name: str, node: ast.AST, operation: str = 'assign', *, walrus: bool = False) -> None:
        if not self._is_global(name, walrus=walrus):
            return
        # 函数中的 global 声明可能延后执行，不能证明入口已在模块加载时定义。
        effective = [scope for scope in self.scopes if scope.kind != 'comprehension'] if walrus else self.scopes
        if all(scope.kind == 'module' for scope in effective):
            self.module_bindings.add(name)
            self.module_binding_counts[name] = self.module_binding_counts.get(name, 0) + 1
        if name in self.protected:
            self.writes.append({'symbol': name, 'line': getattr(node, 'lineno', 0), 'operation': operation})

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self._bind(node.id, node, 'delete' if isinstance(node.ctx, ast.Del) else 'assign')

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit(node.annotation)
        # NAME: str 仅声明注解，没有改变已注入的外部绑定。
        if node.value is not None:
            self.visit(node.value)
            self.visit(node.target)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Name) and target.id == node.value.id:
                continue
            self.visit(target)
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Lambda) and self.scopes[-1].kind == 'module':
                self.callables.setdefault(target.id, []).append(node.value)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        self._bind(node.target.id, node.target, 'named_expression', walrus=True)

    def _function(self, node) -> None:
        for value in [*node.decorator_list, *node.args.defaults, *node.args.kw_defaults]:
            if value is not None:
                self.visit(value)
        self._bind(node.name, node, 'function_definition')
        if self.scopes[-1].kind == 'module':
            self.callables.setdefault(node.name, []).append(node)
        self.scopes.append(_Scope('function', _declarations(node.body)))
        for statement in node.body:
            self.visit(statement)
        self.scopes.pop()

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for value in [*node.args.defaults, *node.args.kw_defaults]:
            if value is not None:
                self.visit(value)
        self.scopes.append(_Scope('function', set()))
        self.visit(node.body)
        self.scopes.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for value in [*node.decorator_list, *node.bases, *(keyword.value for keyword in node.keywords)]:
            self.visit(value)
        self._bind(node.name, node, 'class_definition')
        self.scopes.append(_Scope('class', _declarations(node.body)))
        for statement in node.body:
            self.visit(statement)
        self.scopes.pop()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._bind(alias.asname or alias.name.split('.')[0], node, 'import')

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == '*':
                self.dynamic_binding = True
            else:
                self._bind(alias.asname or alias.name, node, 'import')

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type:
            self.visit(node.type)
        if node.name:
            self._bind(node.name, node, 'exception_binding')
        for statement in node.body:
            self.visit(statement)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.pattern:
            self.visit(node.pattern)
        if node.name:
            self._bind(node.name, node, 'pattern_binding')

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name:
            self._bind(node.name, node, 'pattern_binding')

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        self.generic_visit(node)
        if node.rest:
            self._bind(node.rest, node, 'pattern_binding')

    def _comprehension(self, node) -> None:
        self.visit(node.generators[0].iter)
        self.scopes.append(_Scope('comprehension', set()))
        for index, generator in enumerate(node.generators):
            if index:
                self.visit(generator.iter)
            self.visit(generator.target)
            for condition in generator.ifs:
                self.visit(condition)
        if isinstance(node, ast.DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            self.visit(node.elt)
        self.scopes.pop()

    visit_ListComp = _comprehension
    visit_SetComp = _comprehension
    visit_DictComp = _comprehension
    visit_GeneratorExp = _comprehension

    def _known_condition(self, node) -> bool | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            value = self._known_condition(node.operand)
            return not value if value is not None else None
        if (not self.globals_shadowed and isinstance(node, ast.Compare) and len(node.ops) == 1
                and isinstance(node.left, ast.Constant) and node.left.value in self.protected
                and isinstance(node.comparators[0], ast.Call)):
            call = node.comparators[0]
            if isinstance(call.func, ast.Name) and call.func.id == 'globals' and not call.args and not call.keywords:
                if isinstance(node.ops[0], ast.In):
                    return True
                if isinstance(node.ops[0], ast.NotIn):
                    return False
        return None

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        known = self._known_condition(node.test)
        for statement in ([] if known is False else node.body):
            self.visit(statement)
        for statement in ([] if known is True else node.orelse):
            self.visit(statement)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in ('exec', 'eval', 'globals', 'locals', '__import__'):
            self.dynamic_binding = True
        self.generic_visit(node)


def _inspect_signature(spec: dict) -> inspect.Signature:
    parameters = []
    for item in spec['parameters']:
        kind = getattr(inspect.Parameter, item['kind'])
        default = inspect.Parameter.empty
        if not item['required'] and kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            default = item.get('default_ast')
        parameters.append(inspect.Parameter(item['name'], kind, default=default))
    return inspect.Signature(parameters)


def _signature_mismatch(expected: dict, node) -> str:
    """检查公开调用形式的兼容性；允许额外可选参数，不执行默认表达式或函数体。"""
    actual = _signature_spec(node, mode='python_signature', source='candidate')
    positional = [item for item in actual['parameters'] if item['kind'] in ('POSITIONAL_ONLY', 'POSITIONAL_OR_KEYWORD')]
    variadic = any(item['kind'] == 'VAR_POSITIONAL' for item in actual['parameters'])
    if expected['mode'] == 'documented_arguments':
        names = expected['names']
        if not variadic and [item['name'] for item in positional[:len(names)]] != names:
            return 'Preserve the public argument names and their documented order.'
        try:
            _inspect_signature(actual).bind(*([object()] * len(names)))
        except TypeError:
            return 'The entry point does not accept the documented positional arguments.'
        return ''
    if expected['async'] != actual['async']:
        return 'Preserve the explicitly stated synchronous or asynchronous interface.'
    expected_signature = _inspect_signature(expected)
    actual_signature = _inspect_signature(actual)
    expected_parameters = list(expected_signature.parameters.values())
    expected_positional = [item for item in expected_parameters if item.kind in (item.POSITIONAL_ONLY, item.POSITIONAL_OR_KEYWORD)]
    for kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
        if any(item.kind == kind for item in expected_parameters) and not any(item.kind == kind for item in actual_signature.parameters.values()):
            return 'Preserve the explicitly stated variadic interface.'
    # 遍历公开位置/关键字分界和有/无可选参数；不是枚举隐藏测试输入。
    for positional_count in range(len(expected_positional) + 1):
        for include_optional in (False, True):
            args = [object()] * positional_count
            kwargs = {item.name: object() for item in expected_parameters
                      if item.kind in (item.POSITIONAL_OR_KEYWORD, item.KEYWORD_ONLY)
                      and item not in expected_positional[:positional_count]
                      and (include_optional or item.default is inspect.Parameter.empty)}
            try:
                expected_signature.bind(*args, **kwargs)
            except TypeError:
                continue
            try:
                actual_signature.bind(*args, **kwargs)
            except TypeError:
                return 'The entry point rejects a call form allowed by the public signature.'
    for item in expected['parameters']:
        if item['default_ast'] is None:
            continue
        counterpart = next((value for value in actual['parameters'] if value['name'] == item['name']), None)
        if counterpart and counterpart['default_ast'] != item['default_ast']:
            return 'Preserve defaults explicitly present in the public signature.'
    return ''


def check_public_contract(code: str, requirements: dict) -> dict:
    """修复选优阶段：源码＋冻结公开规则→静态证据；不运行代码、不使用正式分数、不写库。

    pass 仅表示 check_ids 列明的静态检查未发现违规，不是完整契约/F/S 通过。
    语法失败仍是已测的公开缺陷；动态命名、环境、输入输出语义保持未测量。
    """
    digest = hashlib.sha256(json.dumps(requirements, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
    entry_point = requirements.get('entry_point', '')
    protected = {item['name']: item for item in requirements.get('protected_bindings', [])}
    check_ids = ['public.syntax_invalid:python']
    if entry_point:
        check_ids.append('public.entrypoint_missing:' + entry_point)
    if requirements.get('signature'):
        check_ids.append('public.signature_mismatch:' + entry_point)
    check_ids.extend('public.external_binding_rebound:' + name for name in sorted(protected))
    result = {
        'schema_version': _RESULT_VERSION, 'source': 'public_contract_static',
        'measured': False, 'status': 'unmeasured', 'contract_digest': digest,
        'check_ids': check_ids, 'violations': [],
        'measured_check_ids': [], 'unmeasured_check_ids': list(check_ids),
        'unmeasured': list(requirements.get('unmeasured', [])),
        'functional': 'unmeasured', 'security': 'unmeasured',
    }
    if requirements.get('language', 'python') not in ('python', 'py', 'python3'):
        result['unmeasured'].append('unsupported_language')
        return result

    def violation(rule: str, symbol: str, message: str, source: str, lines=(), operations=()) -> None:
        locations = sorted(set(lines))
        result['violations'].append({'id': rule + ':' + symbol, 'rule_id': rule, 'symbol': symbol,
                                     'line': locations[0] if locations else 0, 'locations': locations,
                                     'operations': sorted(set(operations)), 'message': message,
                                     'public_source': source})

    result['measured'] = True
    measured_ids = {'public.syntax_invalid:python'}

    def record_coverage() -> None:
        """分别记录计划范围与实际可测范围；未知规则不能被误当作已经修复。"""
        result['measured_check_ids'] = [item for item in check_ids if item in measured_ids]
        result['unmeasured_check_ids'] = [item for item in check_ids if item not in measured_ids]

    try:
        tree = ast.parse(code)
        compile(tree, '<public-contract-candidate>', 'exec')
    except (SyntaxError, ValueError, TypeError) as exc:
        violation('public.syntax_invalid', 'python', 'Candidate code must be valid Python.',
                  'language', [getattr(exc, 'lineno', 0) or 0])
        result['status'] = 'fail'
        result['unmeasured'].append('remaining_static_checks_after_syntax_error')
        record_coverage()
        return result
    visitor = _BindingVisitor(set(protected), tree)
    visitor.visit(tree)
    for name, binding in protected.items():
        measured_ids.add('public.external_binding_rebound:' + name)
        writes = [item for item in visitor.writes if item['symbol'] == name]
        if writes:
            violation('public.external_binding_rebound', name,
                      'Preserve the publicly supplied binding; do not replace or delete it.',
                      binding['public_source'], [item['line'] for item in writes],
                      [item['operation'] for item in writes])
    if entry_point:
        if entry_point in visitor.module_bindings:
            measured_ids.add('public.entrypoint_missing:' + entry_point)
        elif visitor.dynamic_binding:
            result['unmeasured'].append('entry_point_uses_dynamic_binding')
        else:
            measured_ids.add('public.entrypoint_missing:' + entry_point)
            violation('public.entrypoint_missing', entry_point, 'Define the publicly named entry point at module scope.',
                      'entry_point/function_name')
    candidates = visitor.callables.get(entry_point, [])
    if requirements.get('signature') and len(candidates) == 1 and visitor.module_binding_counts.get(entry_point) == 1:
        measured_ids.add('public.signature_mismatch:' + entry_point)
        mismatch = _signature_mismatch(requirements['signature'], candidates[0])
        if mismatch:
            violation('public.signature_mismatch', entry_point, mismatch,
                      requirements['signature']['public_source'], [getattr(candidates[0], 'lineno', 0)])
    elif requirements.get('signature'):
        result['unmeasured'].append('entry_point_signature_not_statically_unique')
    if visitor.dynamic_binding:
        result['unmeasured'].append('dynamic_binding_effects')
    result['status'] = 'fail' if result['violations'] else 'pass'
    record_coverage()
    return result


def contract_check_feedback(result: dict) -> dict:
    """公开修复反馈白名单；不转发候选源码、任意附加字段、正式验证结果或隐藏材料。"""
    allowed = ('id', 'rule_id', 'symbol', 'line', 'locations', 'message', 'public_source')
    violations = []
    for item in result.get('violations', []):
        if isinstance(item, dict):
            violations.append({key: item[key] for key in allowed if key in item})
    return {'source': 'public_contract_static', 'measured': result.get('measured') is True,
            'status': result.get('status', 'unmeasured'), 'violations': violations,
            'scope': 'Only public static rules; functional and security behavior remain unmeasured.'}
