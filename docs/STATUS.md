# Состояние доказательств

## Native Foundation 0.3 (2026-11-05)

Существующий FX payload и архив 0.2 сохранены. Новый C++17 core прошёл 14 112
проверок в Debug и Release; observer прошёл 5 комплексных тестовых сценариев,
включая конкурентные наблюдения. Python suite расширен до 58 тестов: PE/shader
probe, provenance SDK, прежние install/restore и packaging. Локально эти проверки
проходят в Linux. Windows x86 build и D3DCompile проверяются отдельной native CI
задачей; результат нужно смотреть в GitHub Actions текущего коммита.

Реализованы собственный DX9 SDR backend, ReShade API bridge, standalone host и
read-only probe; см. [NATIVE.md](NATIVE.md). SDK интегрирован как лицензированный
неизменённый исходный код. Нативная обработка и observer выключены по умолчанию.
Автоматическая установка по-прежнему ограничена прежними четырьмя FX-файлами.

**Не проверено в игре:** GPU execution, add-on load order, Steam/FusionFix runtime,
выбор depth/engine targets, реальные performance/VRAM и эстетика. Нативный проход
сейчас делает только SDR color/contrast/highlight shoulder; depth, shadows,
reflections, particles, texture/geometry replacement и LOD остаются выключенными
не реализованными engine-модулями. Render graph пока планирует и проверяет
зависимости; произвольного GPU graph executor ещё нет. Наличие host исходника
не является отчётом его успешного GPU-запуска.

Исследование: nfsuc decomp — console scaffold без PC symbols; Modern Fix —
retail 1.1.2.1 + DXVK; ExOpts содержит точные Steam source candidates, но также
запрещённые gameplay изменения. В нативный runtime их адреса и код не перенесены.

## Архив Visual Foundation 0.2

Дата: 2026-11-02. Целевая установка пользователя: Steam, nfs.exe 1.0.0.1,
Windows, 3440×1440, уже работающий FusionFix. Файлы этой установки в облако
не предоставлялись. Отметок успешного запуска игры пока **нет**.

| Модуль | В 0.2 | Доказательства и границы |
|---|---|---|
| Core | Инвентаризация PE/hash/config; изолированный PostFX; журнал/rollback | **Автотесты** временных fixtures на Linux и Windows; PowerShell smoke test пройден. Пользовательский FusionFix/EXE не проверен |
| Lighting | SDR contrast/color/highlight shoulder | **Автотесты** численной модели и профилей; **исходники** ReShade. DX9 compile/калибровка **требуют игры** |
| Shadows & Visibility | Реестр настоящих ключей, manual opt-in studies | **Исходники** FusionFix с commit pin. Улучшение в кадре/VRAM/FPS **требует игры**; LOD/culling **экспериментальны** и выключены |
| Textures | Read-only inventory, DDS header/mip validation, comparison | **Автотесты** синтетических DDS. Извлечение/импорт делегированы внешним инструментам; game roundtrip **требует локальных файлов** |
| Materials & Vehicles | Карта исследований, разделение визуальных и физических полей | **Исследование**; новые материалы не поставляются |
| Particles & FX | План по emitter/texture/blending/performance | **Исследование**; новых emitter patches нет |
| PostFX | Собственный FX, Clean/Hybrid/Cinematic, optional low-res bloom | **Автотесты** ссылок на эффекты/значений. GPU compilation, motion/HUD/MSAA **требуют игры** |

## Что проверяется автоматически

* Узкий allowlist записи: только четыре файла собственного PostFX; сохранность
  существующего EXE, DLL/ASI, INI/CFG и ReShade.ini на тестовых установках.
* Отказ при чужом файле, пользовательском изменении, traversal, symlink/reparse
  path; хеши backup; откат завершённой и прерванной установки/удаления; блокировки.
* DDS truncation, mip chain, format/aspect mismatch; CSV frametime metrics.
* Согласованность техник/uniforms, диапазонов профилей и выключенных экспериментов.
* Ограниченность/монотонность/нейтральность CPU-модели grade (не GPU execution).
* Комплектность, хеши manifest и воспроизводимость ZIP в одном окружении сборки.

Команда: `python tools/build_release.py` запускает тесты и validator до сборки.
Подтверждённый запуск: [GitHub Actions #1](https://github.com/schepxchh/Nfsundercover-remaster/actions/runs/41437812731)
для кода commit `63c92310943cf02e4f9dc0f65c5c5ae31abae15b`, 2026-11-02.
Обе задачи `validate (ubuntu-latest)` и `validate (windows-latest)` завершились
успешно. Windows log: **39 tests, OK**, 2.227 s; PowerShell entry point smoke test
успешен. Сборка и загрузка CI-архивов также успешны. Последующее обновление этого
документа/ZIP не изменяет проверенный исполняемый код. CI использует временные
fixtures, не установленную игру. Наличие workflow само по себе не считается тестом.

Поставляемый ZIP собран в Linux с LF. Хеш архива в репозитории — в соседнем
`.zip.sha256`. Переводы строк при Windows checkout могут менять хеш CI-архива;
воспроизводимость проверяется повторной сборкой в одном окружении.

## Что не доказано

Нет GPU-компиляции ReShadeFX, скриншотов A/B, измерений FPS, VRAM или визуальных
сравнений. Нет подтверждённой совместимости цепочки ReShade/FusionFix/Texture Wizard
на конкретном EXE. Нет полной реконструкции движка, новых теневых алгоритмов,
GI/RT, объёмных лучей, динамического дня/ночи, заменённых EA архивов или ассетов.

Все потенциально рискованные engine-патчи отсутствуют в автоматической установке.
4096 shadows и больший дальний каскад — измеряемые исследования, не гарантированное
улучшение. Упаковка файлов не считается доказательством работы в игре.
