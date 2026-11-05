# NFS Undercover: Definitive Remaster

**Продолжение: Native Foundation 0.3.0.** Добавлены C++17 core/render graph,
собственный DX9 backend и ps_3_0 HLSL, standalone host, официальный ReShade API
bridge и read-only PE/shader probe. Native add-on по умолчанию выключен.
[Сборка и устройство native слоя](docs/NATIVE.md) ·
[Исследование пяти upstream проектов](docs/ENGINE_RESEARCH.md).
Файлы, профили и готовый ZIP 0.2 сохранены; инструкции ниже относятся к FX-слою.
Source ZIP 0.3 дополнительно содержит лицензированные заголовки SDK ReShade.

**Visual Foundation 0.2.0 — первая сборка для локального тестирования.**

Долгосрочный визуальный ремастер Need for Speed: Undercover (2008), DirectX 9.
Цель POWERFUL HYBRID: выразительное солнце, глубокий цвет, чистая дорога и
читаемость на скорости. Физика, управление, AI, прогрессия и SimRate не меняются.

В 0.2 реализованы собственный SDR-шейдер ReShadeFX, три профиля, Windows CLI
диагностики/установки/отката, анализ DDS и воспроизводимый тестовый протокол.
Это ещё не texture pack и не замена геометрии/материалов движка. Игра и GPU в
облаке отсутствуют: **компиляция FX, качество и совместимость Steam 1.0.0.1
требуют запуска на вашем ПК**. Полный статус — [STATUS](docs/STATUS.md).

## Скачать и подготовить

ZIP находится в [artifacts](https://github.com/schepxchh/Nfsundercover-remaster/tree/main/artifacts)
и создаётся командой `python tools/build_release.py`. Рядом SHA256; внутри
`MANIFEST.json` с хешами каждого файла. Распакуйте **в отдельную папку вне игры**.
Архив содержит исходники, инструменты, документацию и лицензированные SDK headers; сторонних DLL/ASI, nfs.exe
и ресурсов EA нет. Правила лицензирования: [THIRD_PARTY.md](THIRD_PARTY.md).

1. Оставьте рабочий FusionFix и 3440×1440 как есть. Не устанавливайте новую версию
   FusionFix поверх существующей ради этого профиля.
2. Установите официальный [Python 3.10+](https://www.python.org/downloads/windows/)
   с Python launcher. Зависимостей pip нет. Команды ниже выполняются из папки ZIP.
3. Пока игра закрыта, выполните диагностику и резервирование:

```powershell
$Game = 'D:\SteamLibrary\steamapps\common\Need for Speed Undercover'
py -3 tools/remaster.py diagnose --game-dir "$Game" --output "$env:USERPROFILE\Desktop\nfsuc-before.json"
py -3 tools/remaster.py backup --game-dir "$Game" --output "$env:USERPROFILE\Desktop\nfsuc-configs-before.zip"
```

Путь — пример, укажите свою папку с `nfs.exe`. Выходной файл должен быть новым и
вне игры. Backup сохраняет найденные INI/CFG и инвентаризацию хешей; он не содержит
игровые архивы, сохранения или бинарники. Сохранения при необходимости копируйте
отдельно. Отчёты содержат локальные пути/настройки — проверьте их перед публикацией.

## ReShade: официальная зависимость

Если ReShade уже работает, сохраните существующие пресеты и пропустите повторную
установку. Иначе скачайте стандартный установщик только с [reshade.me](https://reshade.me/).
Цель шейдера — ReShade **6.0+**, API **DirectX 9**, 32-битная игра. Запишите точную
версию и хеш установленного ReShade в отчёт: номер версии 6.0+ не означает, что
каждая версия уже протестирована. Add-on build и сторонние пакеты эффектов не нужны.

**До установки проверьте diagnose:** имя `d3d9.dll` само по себе не доказывает,
что это ReShade. Если файл уже занят другим wrapper/loader (DXVK, ENB, apitrace
или иной мод), остановитесь и разберите цепочку отдельно. Не заменяйте/переименовывайте
DLL вслепую. `dinput8.dll`, ASI loader и FusionFix остаются на месте. Наш инструмент
не ставит ReShade, не строит цепочку загрузки и не меняет эти файлы.

Первый запуск с ReShade выполните без эффектов и убедитесь, что FusionFix работает.
Официальную установку ReShade при необходимости удаляйте его же установщиком;
это отдельная операция от удаления нашего PostFX.

## Установить PostFX

```powershell
py -3 tools/remaster.py install --game-dir "$Game" --module postfx --dry-run
py -3 tools/remaster.py install --game-dir "$Game" --module postfx
```

Устанавливаются только четыре собственных файла в `nfsuc-remaster/Shaders/` и
`nfsuc-remaster/Profiles/`. Журнал и резервные версии — в `.nfsuc-remaster-state/`.
Существующий чужой или изменённый пользователем файл блокирует операцию.
Альтернативный Windows-вход: `./tools/remaster.ps1` с теми же аргументами, если
текущая политика Windows разрешает скрипты; менять execution policy не требуется.
Основные команды Python не зависят от разрешения PowerShell-скриптов.

В игре откройте ReShade (обычно Home). В Settings добавьте в **Effect search paths**
абсолютный путь `ВАША_ПАПКА_ИГРЫ\nfsuc-remaster\Shaders`, сохранив старые пути.
Texture search paths для этого эффекта не нужны. Выполните Reload.
В Home выберите `nfsuc-remaster\Profiles\Clean.ini` через диалог выбора пресета.
Проверьте лог компиляции; затем выберите основной `Hybrid.ini`.
Наш установщик сохраняет существующий `ReShade.ini` без изменений, поэтому эта
однократная настройка выполняется через интерфейс ReShade.

| Профиль | Характер | Активные техники |
|---|---|---|
| Clean | Минимальное вмешательство, первая проверка | Grade |
| **Hybrid** | Основное направление: цвет, солнце, сдержанные блики | Grade → Bloom |
| Cinematic | Более выраженная тёплая обработка | Grade → Bloom |

Другие эффекты из старых пресетов не должны одновременно работать в сравнении.
Bloom можно отдельно отключить. Sharpen, depth AO, fake RT и LUT не включены.
Результат затрагивает HUD и меню. [Устройство шейдера и ограничения](docs/SHADER.md).

## Тени и видимость

В [FUSIONFIX.md](docs/FUSIONFIX.md) разобраны реальные настройки текущего исходного
кода FusionFix и ограничения VRAM/атласа. Предложены отдельные ручные исследования
ShadowResolution и дальнего каскада. **Они выключены и не применяются установщиком.**
Сначала сопоставьте версию вашего FusionFix: современные `.cfg` и старые `.ini`
нельзя автоматически подменять друг другом. Не вставляйте policy JSON в его конфиг.
LOD/culling остаются отдельным экспериментом. FPSLimit и SimRate сохраняются.

## Удаление и откат

Закройте игру. Сначала выберите прежний ReShade-пресет или выключите наши техники.
Уберите добавленный путь поиска эффектов через Settings, если удаляете модуль.

```powershell
py -3 tools/remaster.py uninstall --game-dir "$Game" --module postfx --dry-run
py -3 tools/remaster.py uninstall --game-dir "$Game" --module postfx
```

`restore` отменяет последнюю завершённую или прерванную транзакцию установщика:
после install — удаляет модуль, после uninstall — возвращает его.

```powershell
py -3 tools/remaster.py restore --game-dir "$Game" --dry-run
py -3 tools/remaster.py restore --game-dir "$Game"
```

Если вы отредактировали установленный профиль, удаление/restore остановятся,
сохранив ваши изменения. Скопируйте изменённый файл вне игры и разрешите конфликт
по записанным хешам; не удаляйте журнал ради обхода проверки. Не редактируйте
установленные профили: для настройки используйте копию с другим именем.
Резерв конфигов ZIP восстанавливается вручную по одному исходному файлу при
закрытой игре; `restore` не распаковывает этот ZIP и не меняет FusionFix.

Состояние/резервы намеренно остаются после uninstall. Их можно архивировать и
удалить вручную только после проверки полного отката: тогда автоматическое restore
больше невозможно. После сбоя процессная блокировка снимается автоматически,
только если PID точно завершён; неоднозначная/повреждённая блокировка останавливает
работу. Не удаляйте lock у работающего установщика. Моделируются прерывания процесса,
а не гарантии сохранности диска при физической потере питания.

## Инструменты разработки

```powershell
py -3 tools/assets.py inventory 'D:\NFSUC-work\extracted' > local-inventory.json
py -3 tools/assets.py dds-info 'D:\NFSUC-work\road.dds'
py -3 tools/assets.py compare-dds 'D:\NFSUC-work\road.dds' 'D:\NFSUC-work\candidate.dds'
py -3 -m unittest discover -s tests -v
py -3 tools/validate.py
py -3 tools/build_release.py
```

DDS preflight проверяет заголовок, размеры, формат и mipmaps; он не импортирует
контейнеры, не оценивает альфа-пиксели и не доказывает совместимость. Подробнее:
[инструменты](docs/TOOLS.md), [asset pipeline](docs/ASSET_PIPELINE.md),
[архитектура рендера](docs/RENDERING.md), [roadmap](docs/ROADMAP.md).

Для теста на ПК используйте [LOCAL_TESTING.md](docs/LOCAL_TESTING.md) и
[шаблон отчёта](docs/TEST_REPORT.md). CI проверяет инструменты и комплектность,
а не запускает Undercover. Правила проекта — [AGENTS.md](AGENTS.md),
проектный скилл — [.agents/skills/nfsuc-visual-modding/SKILL.md](.agents/skills/nfsuc-visual-modding/SKILL.md).

Проект неофициальный, не связан с Electronic Arts. Название игры принадлежит
соответствующим правообладателям; MIT распространяется на оригинальный код проекта.
