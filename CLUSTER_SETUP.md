# EPQ Cluster Setup (SSH)

This guide assumes a Linux SSH cluster environment and no root/sudo access.
It uses a simplified user-local toolchain at ~/.local/opt.

## What must be set up

- Java 21 or newer
- Maven 3.9+
- Environment variables in ~/.bashrc:
  - JAVA_HOME
  - MAVEN_HOME
  - PATH including Java and Maven bin folders

## One-command setup (recommended)

From the repository root:

    python3 ./setup_epq_cluster.py

This installs JDK and Maven under ~/.local/opt, updates ~/.bashrc, and verifies both tools.

To also build EPQ and generate cp.txt in the same command:

    python3 ./setup_epq_cluster.py --build

To build and launch JMONSEL GUI in one command:

    python3 ./setup_epq_cluster.py --run-gui

To build and run a Jython script in one command:

    python3 ./setup_epq_cluster.py --run-script /path/to/your_script.py

After setup, apply environment changes in the current shell:

    source ~/.bashrc

## Manual user-local setup

1. Create local install directories:

    mkdir -p ~/.local/opt ~/.local/bin

2. Download and install JDK 21:

    cd ~/.local/opt
    curl -fL "<https://api.adoptium.net/v3/binary/latest/21/ga/linux/x64/jdk/hotspot/normal/eclipse>" -o jdk21.tar.gz
    tar -xzf jdk21.tar.gz
    rm -f jdk21.tar.gz

Note: This Adoptium URL is a direct download API endpoint (it returns a tar.gz), so opening it in a browser may not show a web page.

1. Download and install Maven:

    cd ~/.local/opt
    curl -fL "<https://downloads.apache.org/maven/maven-3/3.9.16/binaries/apache-maven-3.9.16-bin.tar.gz>" -o maven.tar.gz
    tar -xzf maven.tar.gz
    rm -f maven.tar.gz

2. Add environment variables to ~/.bashrc:

    cat >> ~/.bashrc <<'EOF'
    export JAVA_HOME="$(find ~/.local/opt -maxdepth 1 -type d -name 'jdk-21*' | sort | head -n 1)"
    export MAVEN_HOME="$HOME/.local/opt/apache-maven-3.9.16"
    export PATH="$JAVA_HOME/bin:$MAVEN_HOME/bin:$PATH"
    EOF

3. Apply settings and verify tools:

    source ~/.bashrc

    java -version
    mvn -version

Expected:

- Java reports version 21+
- Maven reports 3.9+

## Build EPQ

From the repository root:

    source ~/.bashrc
    cp pom.template pom.xml
    sed -i 's/NUMBER_VERSION/15.1.48/g' pom.xml
    mvn -DskipTests package
    mvn -q -DincludeScope=runtime dependency:build-classpath -Dmdep.outputFile=cp.txt

## Notes

- No root access is required.
- If the cluster blocks outbound downloads, upload JDK and Maven tar files manually and extract under ~/.local/opt.
