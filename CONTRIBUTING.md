# Руководство по участию в разработке GeminiOS / Contributing Guide

Добро пожаловать в разработку **GeminiOS**! Мы рады любым конструктивным идеям, баг-репортам и пулл-реквестам.

Все изменения в основную ветку принимаются исключительно через **Pull Request (PR)** после ревью и одобрения мейнтейнером [@pon4ikisdonut](https://github.com/pon4ikisdonut).

💬 **Официальный чат разработчиков и комьюнити в Telegram:** [ОПГ «Радуга»](https://t.me/OPG_R4duga)

---

## 1. Архитектура проекта

```text
GeminiOS/
├── build.sh                 # Главный оркестратор сборки (Docker / Native / Tarballs / QEMU)
├── Dockerfile               # Воспроизводимое окружение сборщика (geminios-builder)
├── config/                  # Брендинг, os-release, geminios-release, sysctl
├── geminios-repo/           # Манифесты пакетов (.gem.toml) для менеджера gem
├── src/
│   ├── gem/                 # Собственный пакетный менеджер `gem`
│   ├── geminid/             # Системный ИИ-демон (Gemini API, Gemma fallback, Panic Guard)
│   ├── installer/           # Графический PyQt6 установщик на диск и бэкенд
│   ├── integrations/        # Интеграции: OOBE, Dolphin actions, CLI, shell hooks
│   ├── live-initcpio/       # Initramfs хуки Live-режима (overlayfs, mount)
│   ├── ollama-gemma/        # Локальный офлайн ИИ-помощник
│   └── themes/              # Темы: KDE Plasma 6 M3 Dark, SDDM, Plymouth, GRUB
└── tests/
    └── verify_geminios.py   # Автотесты целостности, синтаксиса и логики
```

---

## 2. Как сделать форк и настроить окружение

1. **Сделайте форк репозитория** на GitHub через кнопку **Fork** в правом верхнем углу или через GitHub CLI:
   ```bash
   gh repo fork pon4ikisdonut/GeminiOS --clone
   cd GeminiOS
   ```

2. **Создайте отдельную ветку** для ваших изменений:
   ```bash
   git checkout -b feat/my-awesome-feature
   # или
   git checkout -b fix/issue-description
   ```

---

## 3. Как собрать и протестировать систему локально

### Рекомендуемый способ: Сборка в Docker (Linux, Windows WSL, macOS)
Для сборки требуется только установленный Docker:
```bash
./build.sh --docker
```
Скрипт автоматически:
- Соберет образ строителя `geminios-builder:1.0.1`
- Развернет независимую glibc + Linux 7.3.5 + KDE Plasma 6 систему
- Упакует squashfs и сгенерирует гибридный UEFI/BIOS ISO в папке `out/GeminiOS-1.0.1-x86_64.iso`

### Запуск в эмуляторе QEMU
После сборки ISO запустите тестовую виртуальную машину одной командой:
```bash
./build.sh --qemu
```

### Запуск автотестов
Перед отправкой изменений обязательно запустите тестовый набор:
```bash
python tests/verify_geminios.py
```
Тест проверяет:
- Синтаксис всех Python-скриптов без компиляционных ошибок.
- Корректность синтаксиса bash/ash скриптов (`bash -n`).
- Валидность TOML-конфигов и манифестов пакетов `gem`.
- Логику агента `geminid`, `hwcheck` и работу `PanicSequenceDetector` для всех запрещенных фраз.
- Целостность ключевых ассетов (логотипы, темы SDDM/GRUB/Plymouth/Plasma, обои, хуки initcpio).

---

## 4. Правила оформления коммитов (Conventional Commits)

Мы используем формат [Conventional Commits](https://www.conventionalcommits.org/):
* `feat:` добавление новой функциональности (например, `feat: add Material 3 volume slider`)
* `fix:` исправление ошибки (например, `fix: resolve grub png loading error`)
* `refactor:` оптимизация или рефакторинг кода без изменения логики
* `perf:` улучшение производительности или ускорение сборки
* `test:` добавление или обновление тестов
* `docs:` правки документации и README
* `chore:` рутинные задачи сборщика и обновление зависимостей

---

## 5. Создание Pull Request (PR)

1. Убедитесь, что `python tests/verify_geminios.py` выдает `ALL GEMINIOS 1.0 VERIFICATION CHECKS PASSED`.
2. Убедитесь, что в коммит **НЕ** попали временные файлы сборщика (`work/`, `out/`, `*.iso`).
3. Запушьте ветку в свой форк:
   ```bash
   git push origin feat/my-awesome-feature
   ```
4. Откройте **Pull Request** в репозиторий `pon4ikisdonut/GeminiOS`.
5. Заполните шаблон PR: опишите изменения и приложите результаты тестов или скриншоты.
6. GitHub Actions автоматически запустит CI для проверки вашего кода.
7. Мейнтейнер (@pon4ikisdonut) проведет код-ревью и примет ваш PR!

---
💬 Вопросы, предложения и помощь: чат **[ОПГ «Радуга»](https://t.me/OPG_R4duga)**
