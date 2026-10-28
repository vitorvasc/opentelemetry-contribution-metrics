/**
 * Calculate translation coverage from a git tree
 * @param {Array} tree - Entries of a recursive git tree
 * @param {string} lang - Language code
 * @returns {object} - { percentage, lang_files, en_files }
 */
export function summarizeCoverage(tree, lang) {
  // Count .md files in content/en/ and content/{lang}/
  const countMarkdown = (prefix) =>
    tree.filter(
      (item) => item.path.startsWith(prefix) && item.path.endsWith(".md"),
    ).length;

  const enFiles = countMarkdown("content/en/");
  const langFiles = countMarkdown(`content/${lang}/`);
  const percentage = enFiles > 0 ? (langFiles / enFiles) * 100 : 0;

  return {
    percentage: Math.round(percentage * 10) / 10, // Round to 1 decimal
    lang_files: langFiles,
    en_files: enFiles,
  };
}

/**
 * Get the full file tree of a tag, branch or commit
 * @param {object} gh - Client from createClient
 * @param {object} repoRef - { owner, repo }
 * @param {string} ref - Tag, branch, commit or HEAD (the default branch)
 * @returns {Array} - Entries of the recursive git tree
 */
export async function fetchTree(gh, { owner, repo }, ref) {
  const data = await gh.ghFetch(
    `/repos/${owner}/${repo}/git/trees/${ref}?recursive=1`,
  );

  if (data.truncated) {
    throw new Error(
      `Git tree for ${ref} is truncated, coverage would be undercounted`,
    );
  }
  return data.tree;
}
