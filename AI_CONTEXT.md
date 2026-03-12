# AI Context — LookAtMe

Project: LookAtMe

Stack:
- Python (Flask)
- Jinja templates
- Vanilla JavaScript
- Prisma ORM
- SQLite
- Fly.io deployment
- PWA (manifest + service worker)

Architecture rules:
- Do NOT refactor project structure
- Do NOT rename files
- Do NOT modify database schema unless explicitly instructed
- Only apply targeted fixes

Core systems implemented:
- Activity feed
- Reactions
- Friends system
- Smart invites
- Spaces (in progress)
- Theme system (light / dark / sunny / sepia)
- Profile system
- PWA install support
- Focus sessions

Branch currently used:
dev

Recent stabilization fixes:
- language switching
- theme persistence
- profile save regression
- smart friend invites
- PWA install logic

Known issues currently being fixed:
- base.html layout regression
- activity feed ignoring theme
- invite friends widget button not wired
- PWA install button visibility logic
- logo accent color inconsistent across themes