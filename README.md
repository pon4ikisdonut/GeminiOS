<h1 align="center">GeminiOS 1.0.1 ("Spark")</h1>

<p align="center">
  <img src="src/themes/logo/geminios-logo.svg" alt="GeminiOS Logo" width="130" height="130" />
</p>

<p align="center">
  <strong>GeminiOS, powered by Linux — With Love, With Gemini</strong><br>
  <em>Независимый Linux-дистрибутив с Material Design 3, системным ИИ Gemini & Gemma, пакетным менеджером <code>gem</code> и аппаратным Panic Guard.</em>
</p>

<p align="center">
  <a href="https://t.me/OPG_R4duga"><img src="https://img.shields.io/badge/Telegram-ОПГ_«Радуга»-2AABEE?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram ОПГ Радуга" /></a>
  <a href="https://github.com/pon4ikisdonut/GeminiOS/actions"><img src="https://img.shields.io/badge/CI-Passing-2ea44f?style=for-the-badge&logo=githubactions&logoColor=white" alt="CI Status" /></a>
  <img src="https://img.shields.io/badge/Release-1.0.1_(Spark)-A8C7FA?style=for-the-badge&logo=linux&logoColor=062E6F" alt="Version 1.0.1" />
  <img src="https://img.shields.io/badge/KDE-Plasma_6_M3-blue?style=for-the-badge&logo=kde&logoColor=white" alt="KDE Plasma 6" />
  <img src="https://img.shields.io/badge/Kernel-Linux_7.3.5-orange?style=for-the-badge&logo=linux&logoColor=white" alt="Linux Kernel 7.3.5" />
</p>

---

## 🌈 Официальное комьюнити

Обсуждение дистрибутива, предложения фич, анонсы обновлений, помощь с установкой и разработка:
👉 **Вступайте в Telegram-чат: [ОПГ «Радуга»](https://t.me/OPG_R4duga)**

---

## ✦ Ключевые особенности GeminiOS

- **Окружение рабочего стола:** **KDE Plasma 6** в стиле **Google Material Design 3 Dark / ChromeOS**:
  - Круглые скругления окон (18px), мягкие тени и акцентный цвет `#A8C7FA`.
  - Панель виджета `Gemini Cloud` с динамическим расширением без обрезки текста.
  - Кастомный экран входа **SDDM** на чистом QtQuick с поддержкой переключения пользователей.
  - Загрузочный экран **Plymouth** и тема **GRUB2** с векторным логотипом GeminiOS (Google G + Sparkle).
  - Набор обоев высокой четкости: `GeminiM3Dark`, `GeminiChromeOS`, `GeminiOLEDMinimal`.
- **Системный ИИ (`geminid`):**
  - Модель **Gemini 3.5 Flash Lite** для облачных запросов, анализа пайпов и системного аудита.
  - Автоматический офлайн-фоллбэк на локальные модели **Gemma** через Ollama (`gemma3:1b` / `4b` / `12b`) при отсутствии интернета или ключа.
  - Интерактивный Spotlight оверлей (`Super + G`) и контекстные действия в Dolphin.
  - Помощник терминала `wtf` для моментального объяснения упавших команд.
  - Режим системного агента (`gemini --agent "..."`) с автоматической классификацией рисков (`SAFE`, `ELEVATED`, `DESTRUCTIVE`).
- **Аппаратный Panic Guard (`panic_guard.py`):**
  - Фоновый перехватчик аппаратного потока evdev на уровне ядра.
  - Защита от деструктивных когнитивных триггеров (`67`, `six seven`, `сик севен`, `я люблю microsoft`).
  - При срабатывании: моментальный сброс графики в текстовый режим `KD_TEXT`, вывод полноэкранного ANSI-экрана паники с `Call Trace`, мигание индикаторов клавиатуры (Caps/Scroll/Num Lock) и вызов настоящего Linux Kernel Panic через SysRq.
- **Собственный пакетный менеджер `gem`:**
  - Децентрализованные манифесты на GitHub в репозитории [pon4ikisdonut/geminios-repo](https://github.com/pon4ikisdonut/geminios-repo).
  - Бесшовные мосты к официальным репозиториям Arch Linux (`core`, `extra`, `multilib`) и AUR (`yay` + `makepkg`).
- **Быстрый графический установщик (`gemini_installer.py`):**
  - Нативная установка на диск с поддержкой UEFI (GPT) и Legacy BIOS.
  - Выбор файловой системы (`ext4`, `btrfs`), настройка swap и пользователей.
  - Встроенный баннер и ссылка на чат **ОПГ «Радуга»**.

---

## 🛠 Быстрая локальная сборка ISO

Для воспроизводимой сборки дистрибутива вам потребуется Docker (работает на Arch, Ubuntu, Debian, Fedora, Windows WSL2 и macOS):

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/pon4ikisdonut/GeminiOS.git
cd GeminiOS

# 2. Запустите сборку гибридного UEFI/BIOS ISO
./build.sh --docker
```

Готовый образ появится в каталоге `out/GeminiOS-1.0.1-x86_64.iso` вместе с контрольной суммой `.sha256`.

### Тестирование образа в QEMU
```bash
./build.sh --qemu
```
*Данные для входа в Live-сессию:* пользователь `gemini`, пароль `gemini` (или `sudo -i` без пароля).

### Сборка релизных пакетов для менеджера `gem`
```bash
./build.sh --repo-tarballs
```

---

## 🚀 Как внести свой вклад (Fork & Pull Requests)

Мы приветствуем пулл-реквесты от всех участников сообщества! Любой желающий может сделать форк, улучшить систему и отправить свои изменения на ревью:

1. **Форкните репозиторий:** Нажмите кнопку **Fork** в правом верхнем углу страницы репозитория [pon4ikisdonut/GeminiOS](https://github.com/pon4ikisdonut/GeminiOS).
2. **Склонируйте свой форк:**
   ```bash
   git clone https://github.com/<ваш-логин>/GeminiOS.git
   cd GeminiOS
   ```
3. **Создайте ветку для новой функции или фикса:**
   ```bash
   git checkout -b feat/super-feature
   ```
4. **Внесите изменения и запустите автотесты:**
   ```bash
   python tests/verify_geminios.py
   ```
   *Все 5 блоков проверок должны выдать `[PASS]`.*
5. **Закоммитьте изменения по стандарту Conventional Commits:**
   ```bash
   git commit -m "feat: add support for new Material 3 icon theme"
   ```
6. **Запушьте ветку и откройте Pull Request:**
   Перейдите на GitHub и откройте **Pull Request** в ветку `main` репозитория `pon4ikisdonut/GeminiOS`.
7. **Ревью и мердж:** Мейнтейнер (@pon4ikisdonut) проверит предложенные изменения и примет ваш PR в дистрибутив!

Подробные инструкции смотрите в документе [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📁 Структура репозитория

| Каталог / Файл | Назначение |
|---|---|
| `build.sh` | Главный скрипт сборки ISO, Docker-контейнера и пакетов |
| `Dockerfile` | Окружение изолированного сборщика `geminios-builder:1.0.1` |
| `config/` | Системный брендинг, `os-release`, `geminios-release`, настройки sysctl |
| `geminios-repo/` | Локальные манифесты репозитория `gem` (`index.json` + `*.gem.toml`) |
| `src/gem/` | Исходный код пакетного менеджера `gem` и bash-completion |
| `src/geminid/` | Системный демон ИИ, бэкенды Gemini/Gemma, агент и Panic Guard |
| `src/installer/` | Графический PyQt6 установщик на диск и бэкенд разметки/установки |
| `src/integrations/` | Первоначальная настройка OOBE, оверлей `Super+G`, плагины Dolphin, CLI |
| `src/live-initcpio/` | Хуки mkinitcpio для Live-носителя (overlayfs и обнаружение метки) |
| `src/themes/` | Оформление: KDE Plasma 6 M3 Dark, SDDM, Plymouth, GRUB2, обои |
| `tests/` | Набор автоматических тестов верификации целостности `verify_geminios.py` |

---

## 💬 Контакты и сообщество

- **Telegram-чат:** [ОПГ «Радуга»](https://t.me/OPG_R4duga)
- **GitHub репозиторий пакетов:** [pon4ikisdonut/geminios-repo](https://github.com/pon4ikisdonut/geminios-repo)
- **Мейнтейнер:** [@pon4ikisdonut](https://github.com/pon4ikisdonut)
- **Лицензия:** GPLv3 / MIT
