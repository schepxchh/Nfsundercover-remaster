# Локальный PE32 и D3D9 probe

`tools/engine_probe.py` читает локальные файлы, выводит JSON и ничего в них не
меняет. Он не запускает EXE, не подключается к процессу, не выгружает игровые
ресурсы и не отправляет данные по сети. Python 3.10+, без pip-зависимостей.

```powershell
py -3 tools/engine_probe.py pe-info 'D:\SteamLibrary\steamapps\common\Need for Speed Undercover\nfs.exe'
py -3 tools/engine_probe.py shader-info 'D:\NFSUC-work\local-pixel-shader.bin'
```

Для сохранения отчёта можно перенаправить stdout в новый файл **вне папки игры**.
Перенаправление выполняет оболочка; сам probe файлов не создаёт. Перед публикацией
проверьте локальный путь и метаданные. Сам EXE и shader bytecode не загружайте в Git.

## PE32: что действительно проверяется

Проверяются DOS/PE подписи, длины COFF/PE32 optional header, число data directories,
границы section table, raw и RVA ranges, перекрытия секций, SizeOfHeaders/SizeOfImage,
переполнение 32-битных адресов и размещение entrypoint. Выводятся SHA256, машина,
предпочтительная база, RVA/VA entrypoint и раскладка секций с флагами read/write/execute.
Точки входа и секции кода не дизассемблируются; байты кода в отчёт не попадают.

Обычная таблица import разбирается с ограничениями на descriptors, thunks и длины
строк. В отчёт попадают только имена функций/ordinal из `d3d9.dll`, включая факт
прямого импорта `Direct3DCreate9`, если он есть. Имена остальных DLL/функций не
публикуются. Отсутствие этого импорта не доказывает отсутствие DX9: delay import,
динамический `GetProcAddress`, загрузчики и runtime-перехваты здесь не исследуются.
PE32+ не поддерживается. Это metadata preflight, не полная реализация Windows loader.

Пределы: файл 256 MiB, 96 секций, 1024 import descriptors, 16384 thunks на DLL,
65536 thunks суммарно, 1024 байта на имя. Неинициализированные импортные данные,
перекрывающиеся раскладки и выход за границы вызывают отказ. Неизвестные UTF-8
последовательности в именах заменяются безопасным replacement character; имена
никогда не исполняются и не используются как пути записи. Symlink/reparse inputs
отклоняются. Код возврата 0 означает успешное чтение метаданных, **не совместимость**;
2 — ошибка формата, ограничение анализа или доступа. Ошибка также представлена JSON.

## Steam candidate: источник и границы вывода

Проверенные исходники ExOptsTeam/NFSUCExOpts, commit
`21cd448b1cd2cf4e4d6ab26796f3860aceb9ea6b`:

- [dllmain.cpp](https://github.com/ExOptsTeam/NFSUCExOpts/blob/21cd448b1cd2cf4e4d6ab26796f3860aceb9ea6b/NFSUCExtraOptions/dllmain.cpp)
  нормализует `AddressOfEntryPoint` к базе `0x400000` и сравнивает VA `0x8AEC55`.
  Сообщение называет Steam 1.0.0.1 и размер 10 584 064 байта. Сам ExOpts проверяет
  entrypoint; размер из сообщения не является его проверкой SHA256.
- [GlobalVariables.h](https://github.com/ExOptsTeam/NFSUCExOpts/blob/21cd448b1cd2cf4e4d6ab26796f3860aceb9ea6b/NFSUCExtraOptions/GlobalVariables.h)
  содержит визуальные кандидаты ForceCarLOD VA `0xD3CED8`, ForceTireLOD VA `0xD3CEDC`.
- [ExtraOptionsStuff.h](https://github.com/ExOptsTeam/NFSUCExOpts/blob/21cd448b1cd2cf4e4d6ab26796f3860aceb9ea6b/NFSUCExtraOptions/ExtraOptionsStuff.h)
  и [INI](https://github.com/ExOptsTeam/NFSUCExOpts/blob/21cd448b1cd2cf4e4d6ab26796f3860aceb9ea6b/NFSUCExtraOptionsSettings.ini)
  показывают соответствующие настройки/записи. Значение `-1` — default настройки
  ExOpts, **не подтверждённое исходное значение глобальной переменной игры**.

`structural_candidate` означает совпадение четырёх landmarks: i386/PE32, размера
из сообщения, предпочтительной базы `0x400000` и нормализованного entrypoint.
База `0x400000` — исследовательское предположение, сверяемое с заголовком, а не
результат осмотра пользовательского Steam EXE. `incompatible_fingerprint` означает
несовпадение этих landmarks, а не повреждённую игру или запрет на иной выпуск.

**Утверждённого allowlist SHA256 нет.** Даже файл с совпавшими landmarks остаётся
`runtime_compatibility: unverified`, `approved_hash_match: false`. Изменённый EXE
может сохранить размер и entrypoint. Ни один результат не разрешает патч памяти,
не подтверждает совместимость DLL и не заменяет тест пользовательской сборки.

Для кандидатов проверяются RVAs `0x93CED8` и `0x93CEDC` (вычитание предполагаемой
базы `0x400000`). Probe показывает секцию, её заявленный writable flag и int32
**только когда все четыре байта присутствуют в initialized raw data**. Для BSS/
virtual tail значение остаётся `null`, `storage: virtual_only`; zero-fill или
`-1` не подставляются. Flags заголовка не доказывают runtime page protections;
значение на диске не равно текущему значению в памяти. Адреса остаются кандидатами
и при иной базе неприменимы без нового исследования. Активных записей нет.

## Shader-info: только framing

Принимается raw D3D9 token stream: длина кратна DWORD, минимум version+END,
верхняя часть version token `0xFFFF` (pixel) или `0xFFFE` (vertex), финальный
DWORD `0x0000FFFF`. Для pixel/vertex 3.0 ставится `sm3_framing_candidate`.
Остальные major/minor сообщаются как `other_shader_model_framing`.

Инструкции, их длины, операнды, комментарии и control flow не декодируются.
Произвольные промежуточные DWORDs могут пройти framing, оставаясь невалидным
шейдером. Поэтому инструмент не сообщает число инструкций, не выдаёт disassembly
или код, не доказывает GPU-компиляцию/совместимость и не заменяет CreatePixelShader/
CreateVertexShader на реальном DX9 устройстве. DXBC/DXIL/FX source здесь не форматы
входа. Анализировать можно только уже доступный локальный файл; извлечения из
игровых ресурсов этот инструмент не реализует.

## Доказательства

**Автотесты:** синтетический PE32 без игровых байтов, import by name/ordinal,
пустая таблица, ошибочные/переполняющиеся RVA и заголовки, section bounds/overlap,
ограничения descriptors/thunks, virtual-only globals, неизвестный SHA256 при
совпавших landmarks, framing pixel/vertex 3.0 и отсутствие изменения входа.

**Исходный код/документация:** перечисленные landmarks ExOpts и структуры PE/D3D9.
Спецификации: [Microsoft PE format](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format),
[D3D9 shader codes](https://learn.microsoft.com/en-us/windows-hardware/drivers/display/shader-codes).

**Требует локального запуска:** пользовательский nfs.exe, actual globals/runtime
page protection, DX9 device, перехват и создание shader objects, совместимость
с FusionFix и любыми add-ons. Содержимое файлов в облако не предоставлялось.
