# Исследование движка: источники и границы нативного модуля

Проверено 5 ноября 2026 года по исходникам и документации. Ни один адрес ниже
не проверен в памяти пользовательского `nfs.exe`. Это исследовательские ссылки
для локального анализатора, а не готовая таблица патчей.
Машиночитаемые факты: [engine-research.json](../configs/engine-research.json).

## 1. Decompilation: версия платформы принципиальна

[`dbalatoni13/nfsuc`, `efa6d94c800e4c6d29a24c75820a0b28bbede3a8`](https://github.com/dbalatoni13/nfsuc/tree/efa6d94c800e4c6d29a24c75820a0b28bbede3a8)
описывает **Wii US RX9E69** и **Xbox 360 prototype SPEED_DEBUG_OPT_EN_US**.
Это не PC Steam 1.0.0.1 и не готовая реконструкция PC DX9 renderer.

Подтверждения:

- [README](https://github.com/dbalatoni13/nfsuc/blob/efa6d94c800e4c6d29a24c75820a0b28bbede3a8/README.md)
  прямо перечисляет консольные версии.
- [configure.py](https://github.com/dbalatoni13/nfsuc/blob/efa6d94c800e4c6d29a24c75820a0b28bbede3a8/configure.py)
  выбирает X360/PPCBE либо GC_WII; Win32/x86 target в списке версий отсутствует.
- На закреплённом коммите в корне нет реализации игры в `src/`; файлы
  [symbols.txt](https://github.com/dbalatoni13/nfsuc/blob/efa6d94c800e4c6d29a24c75820a0b28bbede3a8/config/SPEED_DEBUG_OPT_EN_US/symbols.txt)
  и `splits.txt` намеренно пустые. `config.yml` содержит шаблонный hash.
  Упоминания Most Wanted в инструкции извлечения дополнительно требуют проверки.

Практическая польза сейчас — организация objdiff, учёт платформ, matching и
неизменяемых локальных оригиналов. Здесь нет подтверждённых PC функций теней,
LOD, материалов или готового PC symbol map. Консольные адреса, структуры и
ABI переносить в ASI нельзя. [CC0](https://github.com/dbalatoni13/nfsuc/blob/efa6d94c800e4c6d29a24c75820a0b28bbede3a8/LICENSE)
репозитория не предоставляет права на игровые бинарники/ресурсы EA. В проект
не копируются игровые исходники или извлечённые данные.

## 2. ExOpts: реальные визуальные globals и запрещённые соседние функции

Источник:
[`ExOptsTeam/NFSUCExOpts`, `21cd448b1cd2cf4e4d6ab26796f3860aceb9ea6b`](https://github.com/ExOptsTeam/NFSUCExOpts/tree/21cd448b1cd2cf4e4d6ab26796f3860aceb9ea6b).

[DllMain](https://github.com/ExOptsTeam/NFSUCExOpts/blob/21cd448b1cd2cf4e4d6ab26796f3860aceb9ea6b/NFSUCExtraOptions/dllmain.cpp#L11)
нормализует entrypoint через базу `0x400000` и сравнивает результат с
`0x8AEC55`. Сообщение отказа называет Steam 1.0.0.1 размером 10 584 064 байта.
Сам guard проверяет только entrypoint: размер файла, hash и первоначальные
значения globals этим условием не проверяются. `0x400000` здесь — число в
исходной формуле, а не доказательство `ImageBase` произвольного пользовательского PE.

В [GlobalVariables.h](https://github.com/ExOptsTeam/NFSUCExOpts/blob/21cd448b1cd2cf4e4d6ab26796f3860aceb9ea6b/NFSUCExtraOptions/GlobalVariables.h#L19)
найдены:

| Символ | VA в исходнике | Действие ExOpts | Документированные значения |
|---|---|---|---|
| `_ForceCarLOD` | `0x00D3CED8` | запись `int` при Init | `-1` без принуждения; `0–4` уровни A–E |
| `_ForceTireLOD` | `0x00D3CEDC` | запись `int` при Init | `-1` без принуждения; `0–3` уровни A–D |

Тип записи и чтение настроек подтверждает
[ExtraOptionsStuff.h](https://github.com/ExOptsTeam/NFSUCExOpts/blob/21cd448b1cd2cf4e4d6ab26796f3860aceb9ea6b/NFSUCExtraOptions/ExtraOptionsStuff.h#L240),
диапазоны — [INI](https://github.com/ExOptsTeam/NFSUCExOpts/blob/21cd448b1cd2cf4e4d6ab26796f3860aceb9ea6b/NFSUCExtraOptionsSettings.ini).
Значение `-1` является default настроек ExOpts. Это **не проверка исходных
байтов** оригинального PE или текущей памяти игры. При преобразовании VA → RVA
анализатор сначала обязан проверить PE ImageBase и target evidence; данные в
virtual-only/BSS нельзя читать как соседние байты файла. Даже совпадающие
entrypoint и размер не гарантируют идентичный EXE.

Это подтверждённые кандидаты для отдельного визуального исследования автомобилей:
сначала локальный read-only анализ, затем изолированный opt-in эксперимент с
LOD и восстановлением захваченного значения. Принудительный A-LOD на всех машинах
может увеличить VRAM/draw cost и мерцание. На игровую геометрию collision такой
эксперимент распространять нельзя. Эффект на дальних машинах и стабильность гонки
пока требуют запуска игры.

ExOpts нельзя включить целиком ради этих двух значений. Там есть изменения
traffic/opponent count, GameSpeed, денег, unlocks, pursuit, rev limiter, reverse
input и функций сохранения/переноса позиции. Часть значений gameplay записывается
при Init, а supplied defaults включают Collector's Edition и изменение reverse
input. Эти действия исключены из ремастера.

Особенно важно не копировать обработчик `Thing`, подключаемый вызовом на
`0x7B44EE` (`eDisplayFrame` в комментарии исходника). То, что обработчик вызывается
рендерером, не делает его визуальным: он обслуживает gameplay hotkeys.
Функции `PVehicle_GlareOn/Off` в `InGameFunctions.h` указывают на управление
vehicle FX, но допустимые FX ID и безопасная классификация не установлены.
Не вызывать их с угаданными параметрами.

Лицензия ExOpts — [GPLv3](https://github.com/ExOptsTeam/NFSUCExOpts/blob/21cd448b1cd2cf4e4d6ab26796f3860aceb9ea6b/LICENSE).
Здесь используются факты, названия и ссылки. Реализация ExOpts не копируется в
MIT исходники проекта; при будущем заимствовании кода потребуется отдельно
соблюсти его лицензию.

## 3. Modern Fix: полезная диагностика другой сборки

[`Brdjx/nfs-undercover-modern-fix`, `b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d`](https://github.com/Brdjx/nfs-undercover-modern-fix/tree/b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d)
имеет [MIT](https://github.com/Brdjx/nfs-undercover-modern-fix/blob/b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d/LICENSE).
README и `src/main.c` явно привязывают анализ к **retail/EA 1.1.2.1**.
Заявленный автором игровой прогон относится к этой сборке и его системе.
Это не подтверждение Steam 1.0.0.1 или совместимости с нашим стеком.

Подтверждённая архитектура:

- [d3d9log.c](https://github.com/Brdjx/nfs-undercover-modern-fix/blob/b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d/src/d3d9log.c)
  ищет `Direct3DCreate9` в фиксированном import-thunk диапазоне retail
  `0x00B61000..0x00BCA58C`, затем меняет IAT и vtable `IDirect3D9`.
  Есть диагностика HRESULT и present parameters, повторы CreateDevice и фильтр
  display modes. Фиксированный retail диапазон нельзя переносить на Steam.
- [stateguard.c](https://github.com/Brdjx/nfs-undercover-modern-fix/blob/b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d/src/stateguard.c)
  содержит проверку пяти ожидаемых байтов перед guarded patch функций
  state-block replay по retail VA `0x0074CD80` и `0x0074CEC0`. Это пример
  проверки предпосылок, не универсальные адреса Undercover.
- [README](https://github.com/Brdjx/nfs-undercover-modern-fix/blob/b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d/README.md)
  предлагает `version.dll` и DXVK `d3d9.dll`. Установка рядом с ReShade D3D9
  занимает то же имя proxy DLL. DXVK меняет API исполнения на Vulkan.

Для уже стабильной пользовательской игры автоматическая установка Modern Fix
не нужна и не выполняется. Ремастер не меняет core count, threads, timers,
display modes, CreateDevice fallbacks или аппаратную идентификацию. Совместное
применение не подтверждено: требуется инвентаризация DLL, владельцев хуков и
отдельный baseline. Наличие свободного `version.dll` само по себе не доказывает
совместимость модов.

## 4. FusionFix: существующий владелец визуальных хуков

Дополнительно проверен более новый
[`ThirteenAG/WidescreenFixesPack`, `c9b32a0582123b2356fe1e9b3c5a68b02eb7f067`](https://github.com/ThirteenAG/WidescreenFixesPack/tree/c9b32a0582123b2356fe1e9b3c5a68b02eb7f067/source/NFSUndercover.FusionFix),
датированный 4 ноября 2026. Документ [FUSIONFIX.md](FUSIONFIX.md) сохраняет
прежний pin `2f4fd579` как отдельный снимок 0.2; значения разных snapshots
не следует смешивать.

В новом [PostFX.ixx](https://github.com/ThirteenAG/WidescreenFixesPack/blob/c9b32a0582123b2356fe1e9b3c5a68b02eb7f067/source/NFSUndercover.FusionFix/PostFX.ixx)
есть overlay D3D9, SMAA и gamma на `onEndScene`, освобождение ресурсов перед reset.
`settings.json` теперь задаёт AntiAliasing default 1; старый снимок задавал 0.
По-прежнему существуют CSM/scenery hooks, CFG storage и
`AsiSettings_GetApi`. Сам факт экспорта settings API не доказывает публичный ABI
для подключения сторонних C++ render callbacks. Такой ABI здесь не установлен.

Поэтому новые функции нативного модуля не должны дублировать управление CSM,
scenery, GetTextureInfo или весь EndScene. Для теней следует использовать
подтверждённые настройки установленного FusionFix. Для собственного будущего
DX9 эффекта нужны точное владение устройством, сохранение состояний, Reset/lost
device lifecycle и проверка порядка с ReShade/FusionFix overlay.

В `Misc.ixx` FPSLimit участвует в расчёте SimRate. Не менять его или подобные
параметры даже в нативном плагине. Новый ASI не должен обращаться к main loop,
tick accumulator, vehicle physics, AI, input или DRM.

## Практическое продолжение

1. Read-only probe: PE machine, ImageBase, entrypoint, sections/imports, SHA256,
   metadata визуальных candidates и корректная граница raw/virtual data.
2. Собственный C++ add-on через официальный API ReShade с отключённой обработкой
   по умолчанию и явным статусом unknown-build. В 0.3 реализован такой bridge,
   собственный DX9 backend и standalone host: [NATIVE.md](NATIVE.md).
   Не распространять вымышленные
   expected bytes и не обещать поддержку по одному filename/version string.
3. Перед любым future write: точный target evidence, независимые выключатели,
   проверка области памяти и значения, конфликтующих ASI, захват originals,
   отказ при неизвестной сборке и условный rollback только своих значений.
4. Проверить сцену со множеством автомобилей, переходы LOD на скорости,
   frame times, mirrors/reflections и Alt-Tab. Отдельно подтвердить отсутствие
   изменений характеристик, управления и прогрессии.

Компиляция ASI в Windows CI подтверждает сборку. Она не подтверждает адреса
пользовательского EXE, работоспособность хуков или улучшение картинки.
