## Описание изменений / Description of Changes
<!-- Кратко опишите, какие изменения вносятся в GeminiOS и зачем. -->

## Связанные issue / Related Issues
<!-- Например, Closes #123 -->

## Компоненты, затронутые PR / Affected Components
- [ ] Ядро и сборка ISO (`build.sh`, `Dockerfile`, `src/live-initcpio/`)
- [ ] Системный демон ИИ (`src/geminid/`)
- [ ] Panic Guard (`src/geminid/panic_guard.py`)
- [ ] Графический установщик и OOBE (`src/installer/`, `src/integrations/oobe/`)
- [ ] Темы и оформление (KDE Plasma 6 M3, SDDM, Plymouth, GRUB)
- [ ] Пакетный менеджер `gem` и манифесты (`src/gem/`, `geminios-repo/`)
- [ ] Конфигурации и документация (`config/`, `README.md`)

## Чек-лист проверки / Verification Checklist
- [ ] Локальные тесты пройдены: `python tests/verify_geminios.py` завершился успешно (`[PASS]`).
- [ ] Синтаксис bash проверен (`bash -n build.sh` и т.д.).
- [ ] В коммит НЕ добавлены тяжелые бинарники или файлы сборки (`work/`, `out/`, `*.iso`).
- [ ] Коммиты оформлены в стиле Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`).

---
💬 Чат разработчиков и комьюнити: [ОПГ «Радуга»](https://t.me/OPG_R4duga)
