#!/usr/bin/env python3
"""EPQ bootstrap for SSH clusters using a fixed user-local toolchain path.

Installs JDK and Maven into ~/.local/opt, updates ~/.bashrc, verifies tool
versions, and can optionally build EPQ.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path


def try_download(url: str, out_path: Path) -> bool:
    try:
        with urllib.request.urlopen(url) as response, out_path.open("wb") as f:
            shutil.copyfileobj(response, f)
        return True
    except Exception:
        return False


def download_with_fallbacks(urls: list[str], out_path: Path) -> None:
    for url in urls:
        if try_download(url, out_path):
            return
    raise RuntimeError("Unable to download required artifact from provided URLs.")


def find_jdk_home(install_root: Path, jdk_major: str) -> Path | None:
    matches = sorted(install_root.glob(f"jdk-{jdk_major}*"))
    return matches[0] if matches else None


def update_bashrc(java_home: Path, maven_home: Path, bashrc: Path) -> None:
    block_begin = "# >>> EPQ toolchain >>>"
    block_end = "# <<< EPQ toolchain <<<"

    existing = ""
    if bashrc.exists():
        existing = bashrc.read_text(encoding="utf-8")

    filtered_lines = []
    in_block = False
    for line in existing.splitlines():
        if line == block_begin:
            in_block = True
            continue
        if line == block_end:
            in_block = False
            continue
        if not in_block:
            filtered_lines.append(line)

    if filtered_lines and filtered_lines[-1] != "":
        filtered_lines.append("")

    filtered_lines.extend([block_begin, f'export JAVA_HOME="{java_home}"',
            f'export MAVEN_HOME="{maven_home}"', 'export PATH="$JAVA_HOME/bin:$MAVEN_HOME/bin:$PATH"',
            block_end,])

    bashrc.write_text("\n".join(filtered_lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap user-local Java and Maven for EPQ on SSH clusters.")
    parser.add_argument("--build", action="store_true",help="Build EPQ and generate runtime classpath (cp.txt).",)
    parser.add_argument("--run-gui", action="store_true", 
                        help="Launch JMONSEL via JythonApp GUI after build/classpath prep.",)
    parser.add_argument("--run-script", action="append", default=[], metavar="FILE.py",
                        help="Run one Jython script (can be specified multiple times).", )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent
    install_root = Path.home() / ".local" / "opt"
    jdk_major = "21"
    maven_version = "3.9.16"
    bashrc = Path.home() / ".bashrc"

    install_root.mkdir(parents=True, exist_ok=True)

    print(f"==> Installing to {install_root}")

    java_home = find_jdk_home(install_root, jdk_major)
    if java_home is None:
        print(f"==> Installing JDK {jdk_major} (if missing)")
        jdk_tgz = install_root / f"jdk{jdk_major}.tar.gz"
        jdk_url = (f"https://api.adoptium.net/v3/binary/latest/{jdk_major}/ga/linux/x64/jdk/hotspot/normal/eclipse")
        download_with_fallbacks([jdk_url], jdk_tgz)
        with tarfile.open(jdk_tgz, "r:gz") as tf:
            tf.extractall(install_root)
        jdk_tgz.unlink(missing_ok=True)
        java_home = find_jdk_home(install_root, jdk_major)

    if java_home is None:
        raise RuntimeError(f"Failed to locate installed JDK {jdk_major}.")

    maven_home = install_root / f"apache-maven-{maven_version}"
    if not maven_home.exists():
        print(f"==> Installing Maven {maven_version} (if missing)")
        mvn_tgz = install_root / f"maven-{maven_version}.tar.gz"
        urls = [f"https://downloads.apache.org/maven/maven-3/{maven_version}/binaries/apache-maven-{maven_version}-bin.tar.gz",
                f"https://dlcdn.apache.org/maven/maven-3/{maven_version}/binaries/apache-maven-{maven_version}-bin.tar.gz",
                f"https://archive.apache.org/dist/maven/maven-3/{maven_version}/binaries/apache-maven-{maven_version}-bin.tar.gz",]
        download_with_fallbacks(urls, mvn_tgz)
        with tarfile.open(mvn_tgz, "r:gz") as tf:
            tf.extractall(install_root)
        mvn_tgz.unlink(missing_ok=True)

    print(f"==> Updating {bashrc}")
    update_bashrc(java_home, maven_home, bashrc)

    env = os.environ.copy()
    env["JAVA_HOME"] = str(java_home)
    env["MAVEN_HOME"] = str(maven_home)
    env["PATH"] = f"{java_home}/bin:{maven_home}/bin:{env.get('PATH', '')}"

    print("==> Verifying tools")
    subprocess.run(["java", "-version"], check=True, env=env)
    subprocess.run(["mvn", "-version"], check=True, env=env)

    want_runtime = args.build or args.run_gui or len(args.run_script) > 0
    if want_runtime:
        print("==> Building EPQ")
        pom_template = repo_root / "pom.template"
        if not pom_template.exists():
            raise RuntimeError(f"Could not find pom.template in {repo_root}")
        pom_xml = repo_root / "pom.xml"
        text = pom_template.read_text(encoding="utf-8")
        pom_xml.write_text(text.replace("NUMBER_VERSION", "15.1.48"), encoding="utf-8")
        subprocess.run(["mvn", "-DskipTests", "package"], cwd=repo_root, check=True, env=env)

        print("==> Building runtime classpath (cp.txt)")
        subprocess.run(["mvn", "-q", "-DincludeScope=runtime", "dependency:build-classpath", "-Dmdep.outputFile=cp.txt"],
            cwd=repo_root, check=True, env=env,)

    if args.run_gui or len(args.run_script) > 0:
        cp_path = repo_root / "cp.txt"
        if not cp_path.exists():
            raise RuntimeError("cp.txt not found. Build/classpath step did not complete.")
        cp_text = cp_path.read_text(encoding="utf-8").strip()
        java_cp = f"target/classes:{cp_text}"
        java_cmd_base = ["java", "-cp", java_cp, "gov.nist.microanalysis.JythonGUI.JythonApp",]

        if args.run_gui:
            print("==> Launching JMONSEL GUI")
            subprocess.run(java_cmd_base, cwd=repo_root, check=True, env=env)

        for script in args.run_script:
            print(f"==> Running Jython script: {script}")
            subprocess.run(java_cmd_base + [script], cwd=repo_root, check=True, env=env)

    print("\nDone.")
    print("To use this toolchain in the current shell, run:")
    print("  source ~/.bashrc")
    print("Build + runtime classpath from repo root:")
    print("  python3 ./setup_epq_cluster.py --build")
    print("Launch GUI (build/classpath included):")
    print("  python3 ./setup_epq_cluster.py --run-gui")
    print("Run a script (build/classpath included):")
    print("  python3 ./setup_epq_cluster.py --run-script /path/to/script.py")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
