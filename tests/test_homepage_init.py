import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ENTRYPOINT_SCRIPT = REPO_ROOT / "docker-entrypoint-nas.sh"
DEFAULT_CONFIG_DIR = REPO_ROOT / "config"


class EntrypointUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="nas_homepage_test_"))
        self.config_dir = self.tmpdir / "config"
        self.sync_dir = self.tmpdir / "repo-sync"
        self.fake_upstream = self.tmpdir / "fake-upstream.sh"
        self.upstream_args_log = self.tmpdir / "upstream-args.txt"
        self.fake_upstream.write_text(
            f'#!/bin/sh\nprintf "%s\\n" "$*" > "{self.upstream_args_log}"\n',
            encoding="utf-8",
        )
        os.chmod(self.fake_upstream, 0o755)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def run_entrypoint(self, extra_env=None, args=None):
        env = os.environ.copy()
        env.update(
            {
                "HOMEPAGE_CONFIG_DIR": str(self.config_dir),
                "HOMEPAGE_DEFAULT_CONFIG_DIR": str(DEFAULT_CONFIG_DIR),
                "HOMEPAGE_SYNC_DIR": str(self.sync_dir),
                "HOMEPAGE_UPSTREAM_ENTRYPOINT": str(self.fake_upstream),
                "SKIP_UPSTREAM_ENTRYPOINT": "false",
                "AUTO_SYNC_GITHUB": "false",
            }
        )
        if extra_env:
            env.update(extra_env)
        cmd = ["sh", str(ENTRYPOINT_SCRIPT)] + (args or ["node", "server.js"])
        return subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)

    def test_shell_syntax_valid(self):
        proc = subprocess.run(
            ["sh", "-n", str(ENTRYPOINT_SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_seeds_empty_config_dir_and_forwards_args(self):
        proc = self.run_entrypoint(args=["node", "server.js"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for name in ["settings.yaml", "widgets.yaml", "services.yaml", "bookmarks.yaml"]:
            dest = self.config_dir / name
            self.assertTrue(dest.exists(), f"Missing seeded file: {name}")
            self.assertEqual(
                dest.read_text(encoding="utf-8"),
                (DEFAULT_CONFIG_DIR / name).read_text(encoding="utf-8"),
            )
        self.assertEqual(self.upstream_args_log.read_text(encoding="utf-8").strip(), "node server.js")

    def test_preserves_existing_user_configs_when_auto_sync_disabled(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        custom_settings = self.config_dir / "settings.yaml"
        custom_settings.write_text("title: My Custom NAS\n", encoding="utf-8")

        proc = self.run_entrypoint()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(custom_settings.read_text(encoding="utf-8"), "title: My Custom NAS\n")
        self.assertTrue((self.config_dir / "services.yaml").exists())

    def test_auto_sync_github_clones_and_updates_from_local_git_repo(self):
        remote_repo = self.tmpdir / "remote-repo"
        (remote_repo / "config").mkdir(parents=True)
        (remote_repo / "config" / "settings.yaml").write_text("title: Synced V1\n", encoding="utf-8")
        subprocess.run(["git", "init", "-b", "main"], cwd=remote_repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "ci@example.com"], cwd=remote_repo, check=True)
        subprocess.run(["git", "config", "user.name", "CI"], cwd=remote_repo, check=True)
        subprocess.run(["git", "add", "."], cwd=remote_repo, check=True)
        subprocess.run(["git", "commit", "-m", "v1"], cwd=remote_repo, check=True, capture_output=True)

        proc1 = self.run_entrypoint(
            extra_env={
                "AUTO_SYNC_GITHUB": "true",
                "GITHUB_REPO": str(remote_repo),
                "GITHUB_BRANCH": "main",
            }
        )
        self.assertEqual(proc1.returncode, 0, proc1.stderr)
        self.assertEqual((self.config_dir / "settings.yaml").read_text(encoding="utf-8"), "title: Synced V1\n")

        (remote_repo / "config" / "settings.yaml").write_text("title: Synced V2\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=remote_repo, check=True)
        subprocess.run(["git", "commit", "-m", "v2"], cwd=remote_repo, check=True, capture_output=True)

        proc2 = self.run_entrypoint(
            extra_env={
                "AUTO_SYNC_GITHUB": "true",
                "GITHUB_REPO": str(remote_repo),
                "GITHUB_BRANCH": "main",
            }
        )
        self.assertEqual(proc2.returncode, 0, proc2.stderr)
        self.assertEqual((self.config_dir / "settings.yaml").read_text(encoding="utf-8"), "title: Synced V2\n")

    def test_rejects_unsafe_git_source_without_crashing(self):
        bad_cases = [
            {"GITHUB_REPO": "-oProxyCommand=evil", "GITHUB_BRANCH": "main"},
            {"GITHUB_REPO": "ext::sh -c id", "GITHUB_BRANCH": "main"},
            {"GITHUB_REPO": "ftp://example.com/repo.git", "GITHUB_BRANCH": "main"},
            {"GITHUB_REPO": "https://github.com/Johntsai0320/homepage.git", "GITHUB_BRANCH": "--upload-pack=evil"},
            {"GITHUB_REPO": "https://github.com/Johntsai0320/homepage.git", "GITHUB_BRANCH": "main;id"},
            {"GITHUB_REPO": "https://github.com/Johntsai0320/homepage.git", "GITHUB_BRANCH": "main branch"},
        ]
        for case in bad_cases:
            proc = self.run_entrypoint(extra_env={"AUTO_SYNC_GITHUB": "true", **case})
            self.assertEqual(proc.returncode, 0, f"Container should still start on invalid sync config: {case}")
            self.assertIn("Invalid GITHUB_REPO or GITHUB_BRANCH", proc.stderr)


class RepoManifestRegressionTests(unittest.TestCase):
    def test_yaml_configs_and_service_substitution(self):
        settings = yaml.safe_load((DEFAULT_CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8"))
        widgets = yaml.safe_load((DEFAULT_CONFIG_DIR / "widgets.yaml").read_text(encoding="utf-8"))
        bookmarks = yaml.safe_load((DEFAULT_CONFIG_DIR / "bookmarks.yaml").read_text(encoding="utf-8"))
        services_raw = (DEFAULT_CONFIG_DIR / "services.yaml").read_text(encoding="utf-8")

        self.assertEqual(settings["language"], "zh-Hant")
        self.assertTrue(isinstance(widgets, list) and len(widgets) >= 3)
        self.assertTrue(isinstance(bookmarks, list) and len(bookmarks) >= 1)

        env_text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        env_vars = {}
        for line in env_text.splitlines():
            s = line.strip()
            m = re.match(r"^([A-Z][A-Z0-9_]+)=(.*)$", s)
            if m:
                env_vars[m.group(1)] = m.group(2)

        non_comment = "\n".join(l for l in services_raw.splitlines() if not l.lstrip().startswith("#"))
        placeholders = set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", non_comment))
        for p in placeholders:
            self.assertIn(p, env_vars, f"Placeholder {p} missing in .env.example")

        substituted = non_comment
        for k, v in env_vars.items():
            substituted = substituted.replace(f"{{{{{k}}}}}", v)
        self.assertNotIn("{{", substituted)

        services_sub = yaml.safe_load(substituted)
        service_groups = [list(item.keys())[0] for item in services_sub]
        layout_groups = list(settings["layout"].keys())
        self.assertEqual(service_groups, layout_groups)

        for group in services_sub:
            for _, items in group.items():
                for entry in items:
                    for sname, cfg in entry.items():
                        self.assertTrue(
                            cfg["href"].startswith(("http://", "https://")),
                            f"Invalid href for {sname}: {cfg['href']}",
                        )

    def test_compose_synology_json_and_env_parity(self):
        compose_text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        compose = yaml.safe_load(compose_text)
        svc = compose["services"]["homepage"]

        self.assertEqual(svc["build"], ".")
        self.assertEqual(svc["image"], "${HOMEPAGE_IMAGE:-ghcr.io/johntsai0320/homepage:latest}")
        self.assertEqual(svc["mem_limit"], "192m")
        self.assertEqual(svc["memswap_limit"], "256m")
        self.assertIn("host.docker.internal:host-gateway", svc["extra_hosts"])
        self.assertEqual(svc["ports"], ["${HOMEPAGE_BIND_IP:-0.0.0.0}:${HOMEPAGE_PORT:-3010}:3000"])
        self.assertIn("./config:/app/config", svc["volumes"])
        self.assertFalse(any("docker.sock" in v for v in svc["volumes"]))

        compose_env_keys = {item.split("=", 1)[0] for item in svc["environment"]}

        env_text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        documented_env_keys = {
            m.group(1)
            for line in env_text.splitlines()
            if (m := re.match(r"^#?\s*([A-Z][A-Z0-9_]+)=", line.strip()))
        }
        compose_vars = set(re.findall(r"\$\{([A-Z0-9_]+)", compose_text))
        self.assertTrue(compose_vars.issubset(documented_env_keys), compose_vars - documented_env_keys)

        synology = json.loads((REPO_ROOT / "synology-docker-config.json").read_text(encoding="utf-8"))
        self.assertEqual(synology["image"], "ghcr.io/johntsai0320/homepage:latest")
        self.assertEqual(synology["name"], "homepage")
        self.assertEqual(synology["memory_limit"], 192 * 1024 * 1024)
        self.assertEqual(
            [(p["container_port"], p["host_port"]) for p in synology["port_bindings"]],
            [(3000, 3010)],
        )
        self.assertEqual(
            [(v["host_volume_file"], v["mount_point"], v["type"]) for v in synology["volume_bindings"]],
            [("/docker/homepage/config", "/app/config", "rw")],
        )
        synology_env_keys = {item["key"] for item in synology["env_variables"]}
        self.assertEqual(synology_env_keys, compose_env_keys)

    def test_dockerfile_and_github_workflow(self):
        dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("FROM ghcr.io/gethomepage/homepage:latest", dockerfile)
        self.assertIn("COPY config /opt/homepage-defaults/config", dockerfile)
        self.assertIn("COPY docker-entrypoint-nas.sh /usr/local/bin/docker-entrypoint-nas.sh", dockerfile)
        self.assertIn('ENTRYPOINT ["/usr/local/bin/docker-entrypoint-nas.sh"]', dockerfile)

        workflow = yaml.safe_load(
            (REPO_ROOT / ".github" / "workflows" / "docker-publish.yml").read_text(encoding="utf-8")
        )
        self.assertIn("verify", workflow["jobs"])
        self.assertIn("build", workflow["jobs"])
        self.assertIn("merge", workflow["jobs"])
        platforms = workflow["jobs"]["build"]["strategy"]["matrix"]["platform"]
        self.assertEqual(platforms, ["linux/amd64", "linux/arm64"])


if __name__ == "__main__":
    unittest.main()
