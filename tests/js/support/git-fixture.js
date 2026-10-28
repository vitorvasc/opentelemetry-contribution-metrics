// Throwaway git repositories for the drift tests. Every git process gets an
// environment without the user's global or system configuration, so commits
// are never signed and no credential helper or URL rewrite applies.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

/**
 * Create a temporary directory with a home directory for git
 * @returns {object} - { root, env }
 */
export function createSandbox() {
  const root = fs.realpathSync(
    fs.mkdtempSync(path.join(os.tmpdir(), "drift-")),
  );
  const home = path.join(root, "home");
  fs.mkdirSync(home);

  const env = {
    PATH: process.env.PATH,
    HOME: home,
    GIT_CONFIG_GLOBAL: os.devNull,
    GIT_CONFIG_NOSYSTEM: "1",
    GIT_AUTHOR_NAME: "Test",
    GIT_AUTHOR_EMAIL: "test@example.invalid",
    GIT_COMMITTER_NAME: "Test",
    GIT_COMMITTER_EMAIL: "test@example.invalid",
  };
  return { root, env };
}

/**
 * Create a repository that serves partial clones over file://
 * @param {string} dir - Repository directory, created when missing
 * @param {object} env - Environment from createSandbox
 * @returns {object} - { dir, url, git, write, remove, commit }
 */
export function createSource(dir, env) {
  const git = (...args) =>
    execFileSync("git", args, { cwd: dir, env, encoding: "utf8" }).trim();

  fs.mkdirSync(dir, { recursive: true });
  git("init", "--quiet", "--initial-branch=main");
  git("config", "uploadpack.allowFilter", "true");
  git("config", "uploadpack.allowAnySHA1InWant", "true");

  return {
    dir,
    url: pathToFileURL(dir).href,
    git,
    write(file, text) {
      const target = path.join(dir, file);
      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.writeFileSync(target, text);
    },
    remove(file) {
      git("rm", "--quiet", file);
    },
    commit(message) {
      git("add", "--all");
      git("commit", "--quiet", "--no-gpg-sign", "-m", message);
      return git("rev-parse", "HEAD");
    },
  };
}

/**
 * Front matter of a localized page
 * @param {string|null} pin - default_lang_commit value, or null for none
 * @param {object} [options]
 * @param {string} [options.title] - Page title
 * @param {string} [options.suffix] - Text after the pin on the same line
 * @returns {string} - Page source
 */
export function page(pin, { title = "Page", suffix = "" } = {}) {
  const pinLine = pin ? `default_lang_commit: ${pin}${suffix}\n` : "";
  return `---\ntitle: ${title}\n${pinLine}---\n\nBody of ${title}.\n`;
}
