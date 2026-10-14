// frontend/src/lib/class-list.ts
//
// Parses school class names such as "5А" or "10 Б" into grade and letter,
// and groups them by grade for the two-step class picker.

export interface ParsedClassName {
  grade: string;
  letter: string;
}

export interface ClassGroup {
  grade: string;
  classes: string[];
}

const CLASS_NAME_RE = /^(\d+)\s*(.*)$/;

export function parseClassName(name: string): ParsedClassName | null {
  const match = CLASS_NAME_RE.exec(name);
  if (!match) return null;
  return { grade: match[1], letter: match[2].trim() };
}

export function groupClassesByGrade(names: string[]): ClassGroup[] {
  const groups = new Map<string, string[]>();
  for (const name of names) {
    const parsed = parseClassName(name);
    if (!parsed) continue;
    const list = groups.get(parsed.grade) ?? [];
    list.push(name);
    groups.set(parsed.grade, list);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([grade, classes]) => ({ grade, classes }));
}
