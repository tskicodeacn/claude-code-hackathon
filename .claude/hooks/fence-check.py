#!/usr/bin/env python3
"""
PreToolUse hook: Anti-Corruption Layer fence.

Blocks any Write or Edit that would introduce JPA, Spring Framework, or Hibernate
implementation details into album-catalog-service/.

Why a hook and not a prompt:
  Prompts express preferences — they can be overridden by context.
  Hooks enforce hard rules — they cannot. A JPA annotation in the new service
  is not "not preferred": it is categorically wrong (Java imports don't work in
  Python). The hook gives the same answer regardless of how the request is phrased.

See: spring-music-master/docs/adr/002-fence-hook-vs-prompt.md
"""

import json
import re
import sys

# Patterns that indicate monolith implementation details leaking into new service.
# Each entry: (regex_pattern, human_readable_explanation)
FORBIDDEN_PATTERNS = [
    (r'@Entity\b',              '@Entity — JPA entity annotation (monolith only)'),
    (r'@Table\b',               '@Table — JPA table mapping (monolith only)'),
    (r'@Column\b',              '@Column — JPA column annotation (monolith only)'),
    (r'@Id\b',                  '@Id — JPA primary key annotation (monolith only)'),
    (r'@GeneratedValue\b',      '@GeneratedValue — JPA ID strategy (monolith only)'),
    (r'@GenericGenerator\b',    '@GenericGenerator — Hibernate extension (monolith only)'),
    (r'import\s+javax\.persistence',   'javax.persistence — old JPA package (monolith only)'),
    (r'import\s+jakarta\.persistence', 'jakarta.persistence — JPA package (monolith only)'),
    (r'import\s+org\.springframework', 'org.springframework — Spring Framework (monolith only)'),
    (r'import\s+org\.hibernate',       'org.hibernate — Hibernate ORM (monolith only)'),
    (r'\bCrudRepository\b',     'CrudRepository — Spring Data interface (monolith only)'),
    (r'@SpringBootApplication\b', '@SpringBootApplication — Spring Boot (monolith only)'),
    (r'@RestController\b',      '@RestController — Spring MVC (monolith only)'),
    (r'@Autowired\b',           '@Autowired — Spring DI (monolith only)'),
]


def is_new_service_path(file_path: str) -> bool:
    normalized = file_path.replace('\\', '/').lower()
    return 'album-catalog-service' in normalized


def find_violations(content: str) -> list[str]:
    return [
        desc
        for pattern, desc in FORBIDDEN_PATTERNS
        if re.search(pattern, content)
    ]


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    tool_name = data.get('tool_name', '')
    tool_input = data.get('tool_input', {})

    if tool_name not in ('Write', 'Edit'):
        sys.exit(0)

    file_path = tool_input.get('file_path', '')
    if not is_new_service_path(file_path):
        sys.exit(0)

    content = (
        tool_input.get('content', '')
        if tool_name == 'Write'
        else tool_input.get('new_string', '')
    )

    violations = find_violations(content)
    if not violations:
        sys.exit(0)

    lines = [
        '',
        '╔══════════════════════════════════════════════════════════════╗',
        '║  FENCE VIOLATION — Anti-Corruption Layer blocked this write  ║',
        '╚══════════════════════════════════════════════════════════════╝',
        f'',
        f'  File:  {file_path}',
        f'',
        f'  The following monolith internals must NOT enter album-catalog-service/:',
    ]
    for v in violations:
        lines.append(f'    ✗  {v}')
    lines += [
        '',
        '  The new service must define its own abstractions.',
        '  Do NOT copy-paste from the monolith — rewrite using Python/FastAPI equivalents.',
        '',
        '  Reference: spring-music-master/docs/adr/002-fence-hook-vs-prompt.md',
        '',
    ]
    print('\n'.join(lines), file=sys.stderr)
    sys.exit(2)


if __name__ == '__main__':
    main()
