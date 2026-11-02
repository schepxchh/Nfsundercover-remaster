# Реестр инструментов и доказательств

Дата исследования: 2026-11-02. Все проверки ниже — **по исходному коду и документации**.
Ни один внешний инструмент в этой облачной итерации не запускался на установленной
Steam-игре. «Поддерживает Undercover» в README не означает проверенную совместимость
с вашим `nfs.exe`, FusionFix, драйвером и набором ASI. Релизы внешних программ в ZIP
не включены; зависимости устанавливаются пользователем из первоисточника.

| Инструмент | Проверенная область применения | Лицензия / поставка | Решение для проекта |
|---|---|---|---|
| [FusionFix](FUSIONFIX.md) | Исправления рендера и реальные параметры из текущего upstream | Проверка отдельно в FUSIONFIX.md | Сохранить уже работающий экземпляр; не обновлять автоматически |
| [UCGT](https://github.com/NI240SX/UCGT/blob/5233fc9369744a4c6b90c942171a2eb93a8f1192/README.md) | Java 15+, CLI/GUI, BIN/BUN; геометрия и текстуры UC | README разрешает использование фрагментов с указанием автора; стандартной LICENSE в корне не найдено, есть заимствованные зависимости | Внешний инструмент для копий; код не вендорится |
| [Texture Wizard](https://github.com/R-033/texwizard/blob/51e7d29c070aa8f9b7c3b44b78fadfda299777a3/README.md) | Дополнительные глобальные пакеты и перенаправление имён текстур, включая world | [GPL v3](https://github.com/R-033/texwizard/blob/51e7d29c070aa8f9b7c3b44b78fadfda299777a3/LICENSE) | Перспективная изолированная замена; не включать ASI до аудита пересечений с FusionFix |
| [Binary](https://github.com/SpeedReflect/Binary/blob/799adf9f3e02b7d70a9a58af44bc8017591cc41c/Readme.md) | BIN/BUN/LZC, коллекции, Endscript, TPK и материалы через Nikki | [GPL v3](https://github.com/SpeedReflect/Binary/blob/799adf9f3e02b7d70a9a58af44bc8017591cc41c/LICENSE) | Общий upstream 2.9.0 **не выбран** для UC; см. UC-форк ниже |
| [Binercover 2.11.0](https://github.com/NI240SX/Binercover/releases/tag/v2.11.0) | UC-форк Binary; исправляет повреждение semitrucks, расширяет коллекции UC | [GPL v3](https://github.com/NI240SX/Binercover/blob/e609593ed8cfbf7fa85eda6774064482f4d4a7f5/LICENSE) | Кандидат для локальных roundtrip на копиях; runtime пока не проверен |
| [Nikki](https://github.com/SpeedReflect/Nikki/blob/b2468b7e4f1ac1efdb29a0c57380dbc90ed1afe7/Nikki/Support.Undercover/Datamap.cs) | UC Datamap содержит Material, SunInfo, TPKBlock, DBModelPart и др. | [MIT](https://github.com/SpeedReflect/Nikki/blob/b2468b7e4f1ac1efdb29a0c57380dbc90ed1afe7/LICENSE); зависимости отдельно | Полезный исходный код структуры данных; не доказательство безопасного roundtrip |
| [NFS-TexEd 1.7](https://nfs-tools.blogspot.com/p/downloads.html) | Официальная страница перечисляет версию 1.7; экспорт/импорт текстур, поддержка UC заявлена автором | Свободная лицензия и полный исходный код не установлены | Пользовательская установка; сначала неизменённый DDS roundtrip, никаких массовых правок |
| [NFS-VltEd 4.6](https://nfs-tools.blogspot.com/p/downloads.html) | Редактор VLT и ModScript; UC включён в [официальное описание 3.0](https://nfs-tools.blogspot.com/2016/08/nfs-vlted-v30-released.html) | Свободная лицензия и полный исходный код не установлены | Только анализ известных визуальных полей на копии; в установщике 0.2 не используется |
| [ReShade](https://github.com/crosire/reshade/blob/7bf9de8b33bcc76c3177007e65d73c72dd0f34c0/README.md) | Инжектор и компилятор ReShadeFX, DX9 backend | [BSD-3-Clause](https://github.com/crosire/reshade/blob/7bf9de8b33bcc76c3177007e65d73c72dd0f34c0/LICENSE.md) | Официальный обычный installer с [reshade.me](https://reshade.me/); наша поставка содержит только собственный FX |
| [ReShade shaders](https://github.com/crosire/reshade-shaders) | Языковая справка и библиотека эффектов | Лицензии по файлам; `Shaders/ReShade.fxh` помечен CC0-1.0 | Наличие ReShade не даёт прав на любой чужой эффект. Профили 0.2 используют только наш shader |
| [DirectXTex](https://github.com/microsoft/DirectXTex/blob/46d1cbea413b316f5e84352a0de8df227f945616/README.md) | DDS, конверсия, mipmaps, BC compression, texconv/texdiag/texassemble; legacy DDS | [MIT](https://github.com/microsoft/DirectXTex/blob/46d1cbea413b316f5e84352a0de8df227f945616/LICENSE) | Офлайн обработка DDS; не понимает контейнеры NFS |
| [apitrace](https://github.com/apitrace/apitrace/blob/c3829c8fc94332f46f7616d9c9ee995b63d9bfc1/docs/USAGE.markdown) | Native D3D9 trace/replay/state inspection, Windows x86 | [MIT](https://github.com/apitrace/apitrace/blob/c3829c8fc94332f46f7616d9c9ee995b63d9bfc1/LICENSE) | Отдельная исследовательская копия; его `d3d9.dll` конфликтует по имени с ReShade |
| [RenderDoc](https://github.com/baldurk/renderdoc/blob/1d83c25876b315c0a13bc6906c7dd82667b09892/README.md) | Поддерживает современные API, **D3D9 не поддерживает** | MIT | Не предлагать как native DX9 capture. Слой перевода изменит исследуемый рендер и потребует отдельной проверки |
| [nfs-tools/Explorer](https://github.com/nfs-tools/Explorer/blob/45e6fc4d4303669d4884cc5832aa24ef7275dd4e/README.md) | Экспериментальный reader; в README отмечен World, UC не отмечен | Для этой итерации не изучена | Не использовать как подтверждённый UC importer |

## Что реально известно о UCGT

Проверен [Geometry Editor README](https://github.com/NI240SX/UCGT/blob/5233fc9369744a4c6b90c942171a2eb93a8f1192/README%20-%20Geometry%20Editor.md).
Автор заявляет поддержку PC world/car/generic геометрии и текстур UC. NIS —
частичная поддержка без bones. glTF/GLB сохраняет больше возможностей; **OBJ
не использовать для дорог и тоннелей с несколькими UV-каналами**. Есть команды
`dump`, `decompile`, `compile`, `replace`; `replace` может обновлять offsets в
block definitions. Это реальные возможности upstream, ещё не проверенные проектом.
Импорт новой геометрии, не совпадающей с существующими именами, не гарантирован.
Автоматическое копирование высоких LOD во все уровни увеличивает нагрузку;
для проекта оно не является улучшением по умолчанию.

Нельзя использовать Collisions Editor или править Havok bounds: это нарушит
неизменность физики. DBModelParts также содержит связанные данные — требуется
проверка конкретных полей, а не импорт чужого полного набора коллекций.

## Texture Wizard: точный build и конфликтные места

В [UC_Address.h](https://github.com/R-033/texwizard/blob/51e7d29c070aa8f9b7c3b44b78fadfda299777a3/UC_Address.h)
явно указан Steam `1.0.0.1`, размер `10,584,064` bytes, EntryPoint VA `0x8AEC55`.
[DllMain](https://github.com/R-033/texwizard/blob/51e7d29c070aa8f9b7c3b44b78fadfda299777a3/dllmain.cpp)
проверяет entrypoint, а не полный SHA256. Совпадение одной величины не удостоверяет
все байты exe. Эти адреса — **документальные сведения**, не патчи проекта.

[TexWizard.h](https://github.com/R-033/texwizard/blob/51e7d29c070aa8f9b7c3b44b78fadfda299777a3/TexWizard.h)
перехватывает загрузку global chunks и GetTextureInfo, заменяет hash текстуры;
пакеты состоят из `textures.bin` и `meta.json`. Последнее присваивание одинакового
исходного hash в map выигрывает. В текущем исходнике есть autoScan `TexturePacks`;
порядок обхода каталогов не следует использовать как стабильный порядок приоритета.
В текущем [FusionFix Input.ixx](https://github.com/ThirteenAG/WidescreenFixesPack/blob/2f4fd579289c67af593b2164f5376bd008de0d35/source/NFSUndercover.FusionFix/Input.ixx)
есть inline hook GetTextureInfo для контроллерных иконок. Это подтверждённое
пересечение по функции, но совпадение фактических адресов и поведение hooks
на установленном exe ещё не проверены. До установки сравнить hook sites и загрузчик
текстур в **своей версии** FusionFix, затем проверить один тестовый пакет.
Никакого обещания совместимости двух ASI.

## Binary и актуальный UC-форк

Не путать одинаковые номера версий разных форков. Текущий общий Binary commit
`799adf9` соответствует 2.9.0. [Автор Undercover Exposed](https://nfsmods.xyz/mod/4014)
предупреждает о несовместимости общего Binary 2.9.0 и ранних Binarius с UC.
У UC-форка [Binercover](https://github.com/NI240SX/Binercover) старый URL
`NI240SX/Binary` теперь перенаправляется. На дату исследования актуален релиз
2.11.0 (`e609593ed8cfbf7fa85eda6774064482f4d4a7f5`, 2026-10-21); его
[README](https://github.com/NI240SX/Binercover/blob/e609593ed8cfbf7fa85eda6774064482f4d4a7f5/Readme.md)
требует .NET Core 3.1 Desktop Runtime x86 и x64. Это внешнее требование инструмента,
не требование нашего Python CLI. Релиз 2.11.0 добавляет EventSequence, но такие
коллекции не относятся к визуальной области и не используются проектом.

## Существующие визуальные моды как источники исследований

* [Natural Lighting / ProStreet Lighting](https://www.nfsaddons.com/downloads/nfsuc/tools/10913/updated-prostreet-lighting-for-undercover.html)
  автора CHA0SHACKER: на странице v1.4 от 2026-09-18 описаны sun/fog/ambient/specular,
  LUT и восстановленные emitter FX; автор заявляет 1.0.0.1–1.1.2.1. ZIP и скрипты
  нами не проверены. Внутри есть заимствованные игровые текстуры: разрешения на
  перепубликацию не установлены. Только ориентир для изучения конкретных полей.
* [Undercover Exposed 1.4.4](https://nfsmods.xyz/mod/4014): демонстрирует масштаб
  работы с world geometry и материалами; связан с разработкой UCGT. Меняет
  handling, карьеру и автомобили, поэтому целиком **не подходит** области проекта.
  Заявленный им day/night cycle не относится к оригинальной игре и в 0.2 не переносится.

Публичные скриншоты не подтверждают ни стабильность, ни FPS, ни лицензии ресурсов.
При последующей оценке проверять сам скрипт и список затронутых коллекций; запрещённые
параметры должны оставаться побайтно неизменными.

## Воспроизводимость исследования

Исходники читались через GitHub connector; инструменты не скачивались в release.
Версии source snapshot выше фиксированы полными commit SHA в ссылках. Для
nfsu360 первоисточник публикует версии без доступного нам pinned source snapshot;
это прямо ограничивает уровень проверки. При локальной установке записать версию,
URL и SHA256 скачанного файла. Новая upstream-версия требует повторного аудита.
