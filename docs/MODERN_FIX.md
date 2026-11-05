# Modern Fix: исходники, границы и применение к native DX9

Исследование: 2026-11-05. Проверен
[Brdjx/nfs-undercover-modern-fix](https://github.com/Brdjx/nfs-undercover-modern-fix/tree/b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d),
commit `b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d` от 2026-09-12.
Лицензия — [MIT, Bradley Jackson, 2026](https://github.com/Brdjx/nfs-undercover-modern-fix/blob/b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d/LICENSE).
Ни исходники, ни DLL проекта не скопированы в наш runtime.

**Вывод:** это полезный пример диагностики старого рендера и Windows compatibility,
но не готовый ремастер и не подтверждённая основа для Steam 1.0.0.1. Его собственная
[таблица Verified on](https://github.com/Brdjx/nfs-undercover-modern-fix/blob/b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d/README.md#verified-on)
относится к retail/EA Download Manager `nfs.exe 1.1.2.1`, Windows 11 и конкретному
Optimus-ноутбуку. Два успешно пройденных автором заезда — данные автора о его
установке; в нашем проекте Modern Fix не запускался. Нельзя переносить эти выводы
на стабильную установку пользователя с другим EXE и FusionFix.

## Что реализовано в действительности

| Часть | Проверенный код | Значение для собственного проекта |
|---|---|---|
| Bootstrap | `version.dll` proxy, lazy forward на системный `version.dll` по абсолютному пути | Само имя DLL не гарантирует отсутствие конфликта: этот proxy также используют другие загрузчики |
| Запуск после loader lock | `DllMain` создаёт worker; тот до 480 раз проверяет imports с интервалом 250 ms | Полезно отделить установку hooks от loader lock; не следует копировать длительный polling или считать CreateThread полным решением lifecycle |
| CPU topology | Перехват `GetSystemInfo` в IAT игры; коррекция count/mask и фильтр caller по `.text` | Не переносится: проект сохраняет работу симуляции, thread pool и CPU-настройки пользователя |
| D3D9 bootstrap | Поиск указателя `Direct3DCreate9` в заданном диапазоне памяти; замена IAT entry | Наш код должен читать PE import descriptors с bounds checks, а не сканировать чужой фиксированный диапазон |
| Создание устройства | Перехват `IDirect3D9::CreateDevice`; log present parameters/HRESULT, до семи fallback попыток | Точная диагностика пригодна; изменение разрешения, windowed mode, refresh и vsync не является графическим улучшением по умолчанию |
| Display modes | Перехваты `GetAdapterModeCount`/`EnumAdapterModes`, dedupe разрешений, выбор refresh ближе к 60 Hz | Не переносится: рабочие 3440×1440 и refresh пользователя уже сохранены FusionFix |
| State guard | Два пятибайтовых JMP с предварительной проверкой prologue, early return при NULL | Не переносится на Steam. Пропуск state block может оставить неправильный render state |
| DXVK | Upstream package устанавливает `d3d9.dll` DXVK и `dxvk.conf` | Это D3D9→Vulkan translation, не native D3D9. Наш runtime не требует и не устанавливает DXVK |

[main.c](https://github.com/Brdjx/nfs-undercover-modern-fix/blob/b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d/src/main.c),
[proxy_version.c](https://github.com/Brdjx/nfs-undercover-modern-fix/blob/b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d/src/proxy_version.c),
[d3d9log.c](https://github.com/Brdjx/nfs-undercover-modern-fix/blob/b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d/src/d3d9log.c),
[stateguard.c](https://github.com/Brdjx/nfs-undercover-modern-fix/blob/b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d/src/stateguard.c).

В исходниках нет per-frame postprocessing, render-target graph, собственного bloom,
улучшенного алгоритма теней или работы с материалами. Они **не** предоставляют
готовый engine overlay. Наш собственный D3D9 слой требует отдельной реализации.

## Привязки к конкретному EXE

В [nfsufix.h](https://github.com/Brdjx/nfs-undercover-modern-fix/blob/b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d/src/nfsufix.h)
жёстко заданы ImageBase `0x400000`, `.text` bounds и IAT GetSystemInfo `0xB61094`.
D3D9 instrumentation ищет pointer в VA `0xB61000..0xBCA58C`;
state guards используют VA `0x74CD80` и `0x74CEC0`. Это **сведения об upstream**, а не
разрешённые адреса нашего проекта. Проверка пяти инструкционных байтов лишь
уменьшает риск ошибочного site и не подтверждает весь executable build.

В изученном bootstrap нет gate по полному SHA256 или resource version EXE. Поэтому
копирование DLL в папку Steam-версии не становится безопасным от наличия нескольких
локальных checks. Отдельно режимный cache keyed по format не является полной
моделью нескольких adapters/devices. Эти ограничения существенны для нового кода.

Пояснения README про причины crashes частично основаны на измерениях одной машины
и интерпретации автора. Наши документы не принимают их за универсальное доказательство
всех проблем Undercover; стабильную игру не требуется «лечить» этим пакетом.

## Почему не копировать установку upstream

[Install.bat](https://github.com/Brdjx/nfs-undercover-modern-fix/blob/b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d/package/Install.bat)
копирует с overwrite `version.dll`, INI, `d3d9.dll`, `dxvk.conf`; резервирует только
имеющийся `d3d9.dll` как `.bak`, также с overwrite. Повторная установка может затереть
ранний backup. [Uninstall.bat](https://github.com/Brdjx/nfs-undercover-modern-fix/blob/b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d/package/Uninstall.bat)
удаляет несколько файлов по имени без проверки ownership/hash. Для изолированного
ремастера эта модель не подходит. Наше требование: явный allowlist, journal,
проверенные backups, conflict refusal и сохранение пользовательских правок.

Разные имена `dinput8.dll`, `version.dll` и `d3d9.dll` устраняют только файловую
коллизию одного имени. Они не доказывают совместимость inline/IAT/vtable hooks,
порядка загрузки, состояния D3D9 и восстановления устройства.

## Архитектура собственного native DX9 слоя

Следующие пункты — **проектные требования**, а не утверждение, что они уже проверены
на игре. Текущий фактический состав описан в README и STATUS.

1. Загрузиться через уже установленный ASI loader, когда это поддержано выбранной
   сборкой. Иметь собственное имя модуля и INI. Не заменять loader FusionFix.
   До hooks записать PE machine, module paths, proxy stack и flags активных modules.
2. Получить реальный D3D9 entrypoint/device через документированные interfaces.
   Generic API interception не требует игровых адресов; доступ к внутренним
   кадрам engine требует отдельной проверенной карты символов/сигнатур Steam build.
   Не путать такой generic слой с интеграцией в native world lighting.
3. Установить hooks как отдельную контролируемую операцию, сохранив предыдущие
   function pointers. Если неизвестный hook уже изменил site — остановить эту
   функцию, а не перезаписывать его. Полная живущая цепочка модов требует теста.
4. Первым режимом сделать observe-only: размеры/форматы targets, multisampling,
   device caps, HRESULT, Reset/lost events. Не менять present parameters, shader
   constants, game memory и simulation. Логи ограничивать по частоте.
5. Для postprocess захватить нужный color surface без GPU→CPU readback в каждом
   кадре, resolve MSAA, рендерить в отдельные targets и возвращать состояния.
   Generic final-frame цвет включает HUD: это нельзя назвать pre-HUD integration.
6. Освобождать свои DEFAULT resources и state blocks **до** исходного Reset,
   пересоздавать после успешного Reset. При ошибке allocation/compile/copy/draw
   пропускать свой эффект и давать исходному кадру продолжиться.
7. Не выгружать DLL с установленными hooks. Удаление файлов выполняется при закрытой
   игре. Нужны tests для создания/потери/восстановления устройства и нескольких scenes.

## Подходящие открытые реализации и ограничения DX9

| Источник, snapshot | Что можно изучать/интегрировать при соблюдении лицензии | Что ещё проверять |
|---|---|---|
| [Dear ImGui DX9 backend](https://github.com/ocornut/imgui/blob/8c8b8fc266e8cd7fac09340c0373abc28732adb0/backends/imgui_impl_dx9.cpp), [MIT](https://github.com/ocornut/imgui/blob/8c8b8fc266e8cd7fac09340c0373abc28732adb0/LICENSE.txt) | Реальный D3D9 debug UI, stateblock Capture, сохранение transforms, device objects lifecycle | Не перехватывать игровой ввод вне открытого меню; отдельный QA reset и неизвестных overlays |
| [MinHook](https://github.com/TsudaKageyu/minhook/tree/8af6b4acae5a9388fd742b56fa79ece89d96f823), [BSD-2-Clause + HDE notices](https://github.com/TsudaKageyu/minhook/blob/8af6b4acae5a9388fd742b56fa79ece89d96f823/LICENSE.txt) | x86/x64 inline trampolines, status codes и queued hooks | Не решает автоматически конфликт двух hooks или mapping конкретного EXE |
| [SafetyHook](https://github.com/cursey/safetyhook/tree/f44cc070a8340f2f26649553c49533475417304d), [BSL-1.0](https://github.com/cursey/safetyhook/blob/f44cc070a8340f2f26649553c49533475417304d/LICENSE) | Современная C++ библиотека inline/mid hooks, RAII | Отдельно проверить compiler/runtime/dependencies и цепочку с FusionFix; не смешивать две библиотеки без причины |
| [SMAA](https://github.com/iryoku/smaa/blob/71c806a838bdd7d517df19192a20f0c61b3ca29d/SMAA.hlsl), [MIT-style](https://github.com/iryoku/smaa/blob/71c806a838bdd7d517df19192a20f0c61b3ca29d/LICENSE.txt) | В исходном HLSL есть `SMAA_HLSL_3`, реально подходящий legacy backend | Потребуются lookup textures, passes, texture slots и собственное качество в движении. В этой итерации не включено |
| [DirectXTex](TOOLS.md) | DDS анализ, legacy formats, mip generation; отдельные D3D9 helpers | Не импортирует контейнеры NFS, не делает BC7/DX10 header допустимым для UC |

Ни одна из перечисленных библиотек не включается автоматически только потому, что
её лицензия разрешает это. При фактическом добавлении исходника сохранить полный
license/notice, pin и указать distribution decision в THIRD_PARTY.md.

Для собственных HLSL использовать реальный `ps_3_0`/`vs_3_0` и
[D3DCompile из D3DCompiler](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/specifying-compiler-targets),
а не DXC/Shader Model 6. Современный compute-based эффект со SM5/6 не переносится
простым переименованием target. Separably filtered bloom и color transforms можно
реализовать пиксельными passes на DX9; GI, volumetrics и shadow changes требуют
данных движка и иной реализации. D3DX9 — deprecated; новые зависимости на него не
добавлять без необходимости и явного решения о redistributable.

## Правила, которые проверяются по документации Microsoft

* [Reset](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3ddevice9-reset):
  release DEFAULT resources, explicit RT/depth surfaces и state blocks перед reset;
  обработать неуспешный reset как отдельное состояние.
* [Lost devices](https://learn.microsoft.com/en-us/windows/win32/direct3d9/lost-devices):
  HRESULT некоторых операций может не отражать фактически отсутствующий вывод.
  В D3D9Ex другое поведение; его поддержку нельзя обещать из проверки D3D9.
* [Texel-to-pixel mapping](https://learn.microsoft.com/en-us/windows/win32/direct3d9/directly-mapping-texels-to-pixels):
  для screen-space transformed quad учитывать `-0.5` pixel offset. Ошибка даёт
  размытие и смещение, особенно заметные в 3440×1440 и identity pass.
* [State blocks](https://learn.microsoft.com/en-us/windows/win32/direct3d9/state-blocks-save-and-restore-state):
  сохранять graphics state; render-target/depth bindings и дополнительные состояния
  должны учитываться явно. Проверить, что утилита не загрязняет кадр при выходе.

**Уровни доказательств:** MIT/BSL/BSD и описанные code paths — проверено по
источникам; native compile может проверяться отдельно CI; работоспособность на
Steam EXE, совместимость overlays, HDR/SDR порядок, pre-HUD stage и FPS — требуют
локального запуска игры. Сборка DLL не подтверждает эти свойства.
