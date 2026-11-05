# Native Foundation 0.3

Собственная C++17 надстройка для Direct3D 9. Она содержит работающие независимые
части будущего ремастера, но ещё не реконструирует PC renderer Undercover.
Текущий GPU-проход — SDR цвет/контраст/блики, без bloom и shadow lift из FX.
Тени, отражения, частицы, модели и LOD в нативном runtime **не изменяются**.
Физика, EXE, SimRate и FPSLimit нигде не записываются.

## Что реализовано

| Слой | Реальное поведение |
|---|---|
| Core | Строгий fail-closed конфиг; capability gates; CPU SDR grade; lost/reset state machine |
| Render graph | Проверка ресурсов, единственных producers, feedback, missing inputs, циклов; стабильный topological order |
| DX9 backend | Собственный ps_3_0 shader, отдельная копия SDR color RT, fullscreen pass, проверка HRESULT/caps, восстановление состояний |
| Official SDK bridge | События ReShade API 20, DX9-only, nfs.exe-only, transient QI surface reference, очистка до Reset |
| Shader observer | Успешно созданные PS/VS2/3: размер, версия, FNV-1a, число наблюдений; лимиты памяти и mutex |
| Standalone host | Без игры: grayscale bands, grade A/B, readback vs CPU, sentinel states, resize/Reset и borrowed-scene path |
| Local probe | PE sections/imports/entrypoint/hash, безопасный raw/virtual RVA анализ; framing DX9 shader tokens |

Graph — уже тестируемый планировщик, но backend пока исполняет фиксированный
copy→grade путь. Общего GPU executor для произвольного графа ещё нет.
State machine проверяется независимо; фактическими COM-ресурсами владеет backend,
а bridge освобождает их по событиям ReShade. Наличие этих компонентов не доказывает
совместимость с неизвестным FusionFix или semantic mapping игровых passes.

## Сборка без файлов игры

Linux: CMake 3.20+, C++17 compiler. Windows: Visual Studio C++ build tools,
Windows SDK, CMake; **Win32/x86** для 32-битного Undercover.
SDK ReShade уже включён как неизменённый BSD source snapshot с хешами и лицензией.
Сеть при сборке не требуется. Чужих DLL/игровых ресурсов в source ZIP нет.

```powershell
cmake -S . -B build/native -A Win32
cmake --build build/native --config Release
ctest --test-dir build/native -C Release --output-on-failure
```

Linux:

```sh
cmake -S . -B build/native -DCMAKE_BUILD_TYPE=Release
cmake --build build/native
ctest --test-dir build/native --output-on-failure
```

`python tools/check_native.py` автоматизирует эти шаги. Если Linux CMake отсутствует,
он собирает portable tests через g++, без проверки Windows кода.
Linux не собирает DX9/add-on. Windows CTest дополнительно вызывает настоящий
`D3DCompile` для `ps_3_0`; это компиляция HLSL, **не выполнение на GPU**.
Тесты C++ используют собственные проверки, работающие и с `NDEBUG`.

## Сначала standalone DX9

Не устанавливая ничего в игру, запустите:

```powershell
.\build\native\native\Release\nfsuc_dx9_host.exe --self-test --capture native-test.ppm
```

Нужен работающий native D3D9 HAL/драйвер. Capture path должен быть новым;
существующий файл сохраняется. PPM — простой RGB-вывод без внешней image library.
Self-test проверяет восемь уровней серого против CPU с допуском 3/255, возврат RT,
viewport, fog/blend, затем освобождение DEFAULT resources, Reset и второй кадр
в уже активной сцене. Он не является полной проверкой всех GPU/состояний.
Без `--self-test` доступно окно: F1 переключает grade, R делает resize/Reset,
Esc завершает. Нет benchmark claims по времени кадра.

## Экспериментальная установка add-on

Обычный ReShade из 0.2 для этого не заменяется автоматически. Дополнение требует
официального **ReShade с полной поддержкой add-ons**, совместимого с SDK API 20.
`register_addon` проверяет API; неизвестные будущие версии не объявлены совместимыми.
Если текущий обычный ReShade работает, можно оставить его и продолжать использовать
FX-профили 0.2; отдельный host позволяет проверять native backend без смены стека.

1. Закрыть игру, сохранить диагноз/config backup по README. Записать хеши DLL/ASI.
2. Проверить официальный add-on build в отдельной тестовой установке, без эффектов.
   Не перезаписывать занятый `d3d9.dll` и не строить неизвестную DLL chain.
3. Собранные `NFSUCNative.addon32` и `native/config/NFSUCNative.ini` положить вместе
   в явно настроенную ReShade папку add-ons. Скопировать только при отсутствии
   одноимённых файлов; хранить рядом SDK LICENSE и PROJECT LICENSE.
4. Оба переключателя по умолчанию 0. Без readable valid config GPU не затрагивается.
   Убедиться в ReShade.log, что зарегистрирован DX9 runtime.
5. Для отдельного теста изменить `Enabled=1`, перезапустить игру. Отключить Grade/
   Bloom и прочую цветокоррекцию старого пресета, чтобы не получить двойную обработку.
   Для пассивного исследования отдельно включить `ObserveShaders=1`.

Автоматический установщик `remaster.py` по-прежнему устанавливает только четыре
собственных FX-файла. Он не устанавливает add-on, не меняет DLL и не управляет
его конфигом. CI даёт отдельный experimental Win32 artifact с лицензиями;
бинарники не помещаются в source ZIP и не заменяют официальные зависимости.

Конфиг — точные ключи `Enabled`, `ObserveShaders`, `Exposure`, `Contrast`,
`Saturation`, `Warmth`, `Shoulder`, `Strength`, без секций. Неизвестный ключ,
дубликат, NaN/inf, нарушение диапазона или gameplay-параметр выключают обработку.
Читается один раз при загрузке; изменения требуют перезапуска.

## Владение DX9 состоянием

В закреплённом ReShade callback `reshade_present` происходит **внутри сцены**, после
восстановления состояния приложения и overlay. Bridge передаёт `scene_already_active=true`;
backend не вызывает вложенный BeginScene и не завершает чужую сцену. Standalone host
по умолчанию владеет собственной сценой, а второй self-test кадр проверяет borrowed path.

Поддержаны только A8R8G8B8/X8R8G8B8 color surfaces и Shader Model 3.0. HDR/FP16,
depth/stencil и неизвестные форматы отвергаются. Color StretchRect копирует в
отдельную sampleable texture; неудачный MSAA resolve приводит к пропуску прохода.
Запрет StretchRect внутри сцены в документации Microsoft относится к дополнительным
ограничениям **depth/stencil**: этот путь depth не использует. Driver support и
стоимость полной копии в 3440×1440 требуют отдельного измерения.

Сохраняются ALL state block, RT/MRT, depth и viewport; RT/depth не полагаются на
state block. Sampler/FVF/shaders/constants/stream state возвращаются; quad учитывает
DX9 -0.5 pixel offset и сбрасывает WRAP0. DEFAULT texture и surface освобождаются
до Reset/destroy_swapchain. Неуспешный setup пропускает draw и возвращает HRESULT.
Ни один callback не передаёт C++ исключение в игру.

Native grade затрагивает игровой HUD **и overlay ReShade**, поскольку запускается
после него. Маска HUD, semantic depth и scene-only composite ещё не реализованы.
SDR shoulder не восстанавливает уже обрезанный свет. Настоящих GI/RT/volumetrics нет.

## Наблюдение и следующие шаги

При включённом ObserveShaders bridge наблюдает только успешные DX9 init_pipeline.
Байткод не сохраняется и не заменяется. Реестр ограничен, FNV — не криптографический
ключ; коллизии возможны. Он не определяет семантику «тень/отражение» по одному hash.
Уже созданные до загрузки add-on шейдеры не попадают в реестр. Сводка metadata
логируется при корректной выгрузке; при аварийном завершении может отсутствовать.

Для следующего этапа нужны локальные наблюдения шейдеров и render targets, точный
build fingerprint, однотипные сцены и измерения. Новые shadows/reflections/particle
модули нельзя включать только по имени shader или консольной структуре.
См. [ENGINE_RESEARCH.md](ENGINE_RESEARCH.md), [MODERN_FIX.md](MODERN_FIX.md),
[ENGINE_PROBE.md](ENGINE_PROBE.md), [ASSET_PIPELINE.md](ASSET_PIPELINE.md).

Откат native: вернуть Enabled=0, закрыть игру, удалить только свои `.addon32` и
конфиг (сохранив пользовательские изменения), вернуться к прежнему ReShade при
его ручной смене. Проверить исходные хеши FusionFix/загрузчиков. Для игрового A/B
применяется LOCAL_TESTING.md; компиляция и синтетический host не заменяют этот этап.
