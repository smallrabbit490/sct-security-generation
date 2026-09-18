# Juliet Java 评测镜像（SeCodePLT 官方 juliet-java-env 的等价定义）。
#
# 用途：`methods/secodeplt_eval/java_executor.py` 的常驻容器基座。
#
# 与官方 data/external/secodeplt_github/executor_docker/docker/juliet-java-env/Dockerfile
# 的差异，以及为什么这样改：
#
#   1. 官方基于 `openjdk:17-jdk-slim` 并装 maven，靠 `mvn dependency:go-offline`
#      预热依赖。本机 Docker Hub 不可达，无法拉取该基础镜像；而且官方
#      `compile-and-test.sh` 里的 `MAVEN_OPTS="-Dmaven.repo.local=/tmp/maven-repo-$$"`
#      会让预热的 `~/.m2` 完全失效，每个任务重新下载整套依赖。
#      这里去掉 Maven，只保留 JDK + 预置 JUnit standalone jar，用
#      `javac` + `java -jar junit-platform-console-standalone.jar` 直接编译运行。
#
#   2. 官方把 juliet-support 和整个 dataset/ 打进镜像（镜像体积大，换数据要重建）。
#      这里不在镜像里放数据：juliet-support 与 JUnit jar 由执行器以**只读**方式
#      挂载（见 java_executor.java_docker_spec 的 readonly_mounts），
#      每任务数据走宿主工作目录挂载。因此本镜像只需一次构建，换数据不用重建。
#
#   3. 只读挂载还有一个安全作用：容器内运行的候选代码不得改写评测工具本身。
#
# 构建（需要能访问 Docker Hub 或已有可用的 JDK 17 基础镜像）：
#   docker build -t safecoder-java-validator:local docker/java-validator
#
# 注意：当前仓库默认 **不构建本镜像**，而是复用本机已有的
# `secevo-java-js-baseplus-validator:current`（同样含 JDK 17 与 javac）。
# 这样做的原因见 docs/docker_eval_backend_analysis.md 第八章 8.6。
# 本文件用于在具备 Docker Hub 访问能力的环境里复现一份干净、用途单一的镜像。

FROM eclipse-temurin:17-jdk

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8

# 评测只需要 JDK 自带的 javac/java；不装 Maven、不装构建工具链。
# 保留 coreutils（timeout）与 bash：执行器用 `timeout -k` 做容器内超时兜底。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        coreutils \
    && rm -rf /var/lib/apt/lists/*

# JUnit 5 控制台启动器（含 API + Engine + Params），与官方 pom.xml 的 JUnit 5.9.2 同代。
# 官方 compile-and-test.sh 的 test-runner.sh 用的也是这个 artifact，只是版本 1.9.3。
ARG JUNIT_VERSION=1.9.3
RUN mkdir -p /opt/junit \
    && curl -fsSL -o /opt/junit/junit.jar \
        "https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/${JUNIT_VERSION}/junit-platform-console-standalone-${JUNIT_VERSION}.jar"

# 工作目录由执行器挂载；这里只声明，不预置数据。
WORKDIR /work
