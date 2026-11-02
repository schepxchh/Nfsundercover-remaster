# План развития после Visual Foundation 0.2

0.2 — исходная инженерная база: собственная постобработка, три профиля,
диагностика, изолированная установка/откат и анализ локальных ресурсов. Визуальный
результат ещё должен пройти компиляцию ReShade/DX9 и игровые сравнения на ПК.

| Модуль | Следующий измеримый шаг | Условие включения |
|---|---|---|
| Core | Диагностика точного exe, FusionFix и proxy stack; собрать исходный baseline | Запуск и возврат к baseline без изменения INI/loader |
| Lighting | Подобрать highlight/contrast на идентичных кадрах четырёх сцен | Нет новых клиппинга, banding и потери видимости в тени |
| Shadows & Visibility | По одному реальному FusionFix параметру; изучить capture shadow passes | Нет shimmer/cascade jumps и приемлемый frametime; LOD/culling off по умолчанию |
| Textures | Roundtrip одной дороги, затем один оригинальный материал с mipmaps | Правильные alpha/format/texture ID, сохранные соседние данные, права на ресурс |
| Materials & Vehicles | Карта известных visual-only Material fields, один кузов/стекло/фара | Нулевой diff physics/collision/performance, отсутствие flicker |
| Particles & FX | Найти один emitter и его текстуру, измерить overdraw | Изменение только картинки, без nitro/traction/gameplay changes |
| Geometry | UC world glTF roundtrip со всеми UV и LOD на одном блоке | Стриминг и offsets сохранены, collision unchanged, rollback |
| PostFX | Реальная компиляция и GPU timing в 3440×1440 | Читаемость на скорости; HUD и menus проверены |

Каждый этап: pinned upstream + лицензия → анализ на копии → автоматические проверки →
отдельный opt-in пакет → локальный A/B тест → обновление статуса доказательств.
Сроки не назначаются до получения реальных измерений. Нет цели увеличить число
эффектов; свет, корректные материалы и согласованные детали важнее числа переключателей.

Исследовательские ветки, пока не обещанные в релизе: доступ к исходным render targets,
реальные sun shafts с глубиной/occlusion, изменение shadow allocation/filtering,
reflection update rate и native material shader replacement. Ни один экранный glow
не будет называться volumetrics, GI или ray tracing. Оригинальная игра не имеет
обычного day/night cycle; новая система времени потребовала бы отдельного проекта
и проверки влияния на геймплей, поэтому в план 0.2 не включена.

Не переносить целиком total conversions (Exposed/Reformed): их физика, AI и
прогрессия противоречат области Definitive Remaster. Можно исследовать публично
описанные визуальные методы и написать собственную реализацию с отдельными правами.
