/* Which "still missing" keyword chips the score card shows. Collapsed: the
   first CHIP_LIMIT and a "+N" toggle for the rest. Expanded: every one of
   them. Pure, so the rule is unit-testable without React. */
export const CHIP_LIMIT = 5;

export function chipWindow(missing: readonly string[], expanded: boolean, limit = CHIP_LIMIT) {
  const shown = expanded ? missing : missing.slice(0, limit);
  return {
    shown,
    hidden: missing.length - shown.length,
    canToggle: missing.length > limit,
  };
}
