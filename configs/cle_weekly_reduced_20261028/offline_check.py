"""实际运行封网集成及调度测试，依据测试结果写验收文件，不派发实验请求。"""
import io
from pathlib import Path
import sys
import unittest
from .scope import ROOT,CONTROL,write


def main():
    sys.path.insert(0,str(ROOT/'tests'))
    loader=unittest.TestLoader()
    suites=[loader.loadTestsFromName(name) for name in
        ('test_cle_weekly_reduced_scope','tests.test_cle_autonomy','tests.test_cle_live_workbench')]
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=1).run(unittest.TestSuite(suites))
    target=CONTROL/'offline_checks_output.txt';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(stream.getvalue(),encoding='utf-8')
    value={'status':'passed' if result.wasSuccessful() else 'failed',
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'network_API_calls':0,'transport':'synthetic HTTP fixtures only; real sockets blocked in integration tests',
        'output':str(target),'command':'python -B -X utf8 -m configs.cle_weekly_reduced_20261028.offline_check'}
    write(CONTROL/'offline_checks.json',value)
    print(value)
    if not result.wasSuccessful():raise SystemExit(1)


if __name__=='__main__':
    main()
