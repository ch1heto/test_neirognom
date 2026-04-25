## Рекомендации по использованию в проекте

### Как использовать эти данные для выбора культуры при старте цикла

На старте цикла backend или мастер запуска должен сопоставлять ограничения конкретного модуля с профилем культуры: доступная площадь, глубина ячейки, тип системы, сколько дней можно ждать до первого результата, насколько допустим риск болтинга, можно ли вести повторный срез, и какие климатические диапазоны реально достижимы. Если модуль маленький и нужен быстрый демо-результат, приоритет даётся lettuce, arugula, basil, pak_choi, microgreen_radish, microgreen_pea. Если допустим более длинный цикл и хочется показать травы, добавляются cilantro, parsley, dill, mint. Если система плохо держит прохладную корневую зону, лучше не ставить spinach как базовую стартовую культуру. [71]

### Как AI-советник должен сравнивать датчики с нормами

Для каждой культуры должны храниться:

- target_range — оптимальный рабочий диапазон;

- warning_low / warning_high — пороги предупреждения;

- critical_low / critical_high — при необходимости более жёсткие пороги;

- priority_weight — насколько параметр важен именно для этой культуры.

Далее советник должен: 1. сравнить реальные значения air_temp, humidity, water_temp, pH, EC, light с target_range; 2. вычислить величину отклонения; 3. назначить статус normal / info / warning / critical; 4. ранжировать рекомендации так, чтобы сначала выводились самые рискованные отклонения, например water_temp для spinach или humidity для microgreens; 5. учитывать длительность отклонения, а не только одно измерение.

Именно длительность выхода из диапазона критична для маленьких гидропонных систем, где инерция низкая, а параметры могут меняться быстро. [72]

### Как использовать pH/EC для предупреждений

pH и EC — самые важные универсальные параметры для компактной гидропоники, потому что они непосредственно влияют на доступность элементов и силу раствора. Практически полезная логика для AI-советника такая:

- если pH ниже диапазона: предупреждать о риске нарушения усвоения, советовать плавную корректировку, а не резкий скачок;

- если pH выше диапазона: предупреждать о риске хлороза и дефицитов, особенно железа;

- если EC ниже диапазона: советовать постепенное усиление питания, если рост слабый и вода не слишком холодная;

- если EC выше диапазона: предупреждать о солевом стрессе, tipburn, грубении листа и рекомендовать разбавление.

Отдельно полезно держать логику сочетаний:

- high_pH + yellow_leaves → высокий приоритет рекомендации проверить железо;

- high_EC + leaf_edge_burn → высокий приоритет рекомендации на разбавление;

- high_water_temp + slow_growth → проверка растворённого кислорода и риска корневых проблем. [73]

### Как использовать историю показателей для предиктивных предупреждений

Лучший AI-советник для сити-фермы должен смотреть не только на текущее значение, но и на тренд. Для этого стоит хранить:

- скользящее среднее за 1 час, 6 часов, 24 часа;

- число минут/часов вне диапазона;

- скорость дрейфа pH и EC;

- суточный паттерн температуры и влажности;

- динамику длины цикла и массы урожая по прошлым выращиваниям.

Тогда можно делать предиктивные алерты, например:

- «pH растёт третий день подряд, через 12–24 часа уйдёт выше целевого диапазона»;

- «вода ежедневно перегревается после включения света, риск корневого стресса увеличивается»;

- «цикл идёт с отставанием от эталона на 3 дня, вероятная причина — низкий свет и слабое питание».

Это особенно полезно для маленьких ферм, где колебания идут быстрее, чем в больших тепличных системах. [72]

### Как строить АгроТехКарту по окончании цикла

По завершении цикла для каждой культуры стоит формировать АгроТехКарту в таком виде:

- slug, сорт, дата посева, дата высадки, дата среза;

- средние значения и экстремумы по air_temp, humidity, water_temp, pH, EC, light;

- число предупреждений и критических событий;

- длительность отклонений;

- фактический срок до сбора;

- тип сбора: single_cut / cut_and_come_again / microgreens_cut;

- число повторных срезов;

- субъективная оценка качества листа;

- вероятные причины проблем;

- какие корректировки сработали лучше всего.

На следующем цикле AI-советник должен использовать эти карты как локальную эмпирическую базу, а не только как «общие знания». Тогда система станет самообучаемой на уровне проекта: например, можно увидеть, что конкретно в вашей установке basil лучше идёт при 23 °C и RH около 50%, а lettuce хуже переносит определённый светильник из-за перегрева листа. [74]

### Почему лучше хранить общий исследовательский файл crops_knowledge_base.md и отдельные файлы crops_data/*.md для backend

Лучше разделить хранилище на два уровня:

crops_knowledge_base.md
Это человекочитаемая исследовательская база: объяснения, обоснования, ссылки на источники, агрономическая логика, компромиссы и caveats. Этот файл нужен для диплома, ревизии диапазонов, работы с научруком и расширения базы.

crops_data/*.md или ещё лучше *.json / *.yaml рядом с markdown-описанием**
Это backend-представление: чистые поля slug, ranges, alerts, advisor_templates, risk_factors, cycle_defaults. Эти файлы нужны приложению, чтобы быстро парсить данные без длинного текста.

Такое разделение полезно по трём причинам:

- исследовательская логика и кодовая логика не смешиваются;

- проще обновлять диапазоны без переписывания всей пояснительной базы;

- легче версионировать систему: можно менять backend-значения и отдельно сохранять научное обоснование. [75]

## Ограничения и замечания

Самые высокоуверенные данные в этой базе относятся к lettuce, spinach, basil, arugula, pak_choi и общим принципам NFT/DWC. По mint, dill, parsley часть диапазонов сильнее опирается на прикладные гидропонные руководства, чем на университетские crop handbooks. По microgreen_radish и microgreen_pea сроки и микроклимат описаны хорошо, но точные универсальные EC-профили в открытых источниках стандартизованы заметно хуже, поэтому выбран консервативный low-input режим и это стоит пометить в backend как confidence: medium для EC/light_intensity у микрозелени. [76]

[1] [2] [29] [34] [71] [72] https://ccd.uky.edu/sites/default/files/2026-02/ccd-cp-63_hydrolettuce_accessible-2.pdf

https://ccd.uky.edu/sites/default/files/2026-02/ccd-cp-63_hydrolettuce_accessible-2.pdf

[3] [45] [46] https://university.upstartfarmers.com/blog/how-to-grow-mint

https://university.upstartfarmers.com/blog/how-to-grow-mint

[4] [5] [7] [8] [10] [75] https://extension.oregonstate.edu/sites/extd8/files/catalog/auto/EM9457.pdf

https://extension.oregonstate.edu/sites/extd8/files/catalog/auto/EM9457.pdf

[6] [50] https://www.johnnyseeds.com/growers-library/herbs/dill/dill-key-growing-information.html?srsltid=AfmBOoouotIg09fPnO5bqxBCmsQUIXEtNpSs6iPmFyOWSBU545FUJDlG

https://www.johnnyseeds.com/growers-library/herbs/dill/dill-key-growing-information.html?srsltid=AfmBOoouotIg09fPnO5bqxBCmsQUIXEtNpSs6iPmFyOWSBU545FUJDlG

[9] [36] [37] [38] https://cea.cals.cornell.edu/files/2019/06/Cornell-CEA-baby-spinach-handbook.pdf

https://cea.cals.cornell.edu/files/2019/06/Cornell-CEA-baby-spinach-handbook.pdf

[11] [12] [15] [16] [17] https://www.johnnyseeds.com/growers-library/herbs/basil/hydroponic-container-basil-guide.html?srsltid=AfmBOoqHW4Svm3TZ_x-wucGQEgZqPq_YgnX0PxcQitXtrFWSe6sZZIhR

https://www.johnnyseeds.com/growers-library/herbs/basil/hydroponic-container-basil-guide.html?srsltid=AfmBOoqHW4Svm3TZ_x-wucGQEgZqPq_YgnX0PxcQitXtrFWSe6sZZIhR

[13] [18] [74] Growing Hydroponic Basil? Read This First - Upstart University

https://university.upstartfarmers.com/blog/hydroponic-basil

[14] [35] [73] https://www.e-gro.org/pdf/E108.pdf

https://www.e-gro.org/pdf/E108.pdf

[19] https://scri-ceaherb.org/pdf/hydroponic-basil-production.pdf

https://scri-ceaherb.org/pdf/hydroponic-basil-production.pdf

[20] https://www.e-gro.org/pdf/2016-4.pdf

https://www.e-gro.org/pdf/2016-4.pdf

[21] [22] [24] [25] https://www.mdpi.com/2073-4395/11/7/1340

https://www.mdpi.com/2073-4395/11/7/1340

[23] [28] https://www.negreenhouse.org/uploads/9/4/8/2/94821076/mattson_hydroponic_systems_negc_7nov2018_for_web.pdf

https://www.negreenhouse.org/uploads/9/4/8/2/94821076/mattson_hydroponic_systems_negc_7nov2018_for_web.pdf

[26] https://journals.ashs.org/downloadpdf/view/journals/hortsci/60/4/article-p601.pdf

https://journals.ashs.org/downloadpdf/view/journals/hortsci/60/4/article-p601.pdf

[27] https://www.johnnyseeds.com/growers-library/vegetables/greens/arugula-key-growing-information.html?srsltid=AfmBOoo0Nw1aZQulr2M1VoueW6jykf45u5ptT0GNonw8X7ffT9EZKjd9

https://www.johnnyseeds.com/growers-library/vegetables/greens/arugula-key-growing-information.html?srsltid=AfmBOoo0Nw1aZQulr2M1VoueW6jykf45u5ptT0GNonw8X7ffT9EZKjd9

[30] [31] [32] [33] cpb-us-e1.wpmucdn.com

https://cpb-us-e1.wpmucdn.com/blogs.cornell.edu/dist/8/8824/files/2019/06/Cornell-CEA-Lettuce-Handbook-.pdf

[39] [40] https://university.upstartfarmers.com/blog/are-you-growing-cilantro-in-hydroponics-read-this-first

https://university.upstartfarmers.com/blog/are-you-growing-cilantro-in-hydroponics-read-this-first

[41] [42] [43] [76] https://university.upstartfarmers.com/blog/growing-hydroponic-parsley

https://university.upstartfarmers.com/blog/growing-hydroponic-parsley

[44] https://www.researchgate.net/publication/350394362_Modeling_growth_and_development_of_hydroponically_grown_dill_parsley_and_watercress_in_response_to_photosynthetic_daily_light_integral_and_mean_daily_temperature

https://www.researchgate.net/publication/350394362_Modeling_growth_and_development_of_hydroponically_grown_dill_parsley_and_watercress_in_response_to_photosynthetic_daily_light_integral_and_mean_daily_temperature

[47] https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0248662

https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0248662

[48] [49] https://igworks.com/blogs/growing-guides/growing-hydroponic-dill?srsltid=AfmBOoq99QGIgObktHTLFm16gKL60ZTPqIYFOiEhzHEwzNKlQCMccvL6

https://igworks.com/blogs/growing-guides/growing-hydroponic-dill?srsltid=AfmBOoq99QGIgObktHTLFm16gKL60ZTPqIYFOiEhzHEwzNKlQCMccvL6

[51] [52] [53] https://university.upstartfarmers.com/blog/growing-bok-choy

https://university.upstartfarmers.com/blog/growing-bok-choy

[54] https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0202090

https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0202090

[55] https://www.johnnyseeds.com/vegetables/greens/pac-choi-bok-choy/joi-choi-f1-green-seed-507.html?srsltid=AfmBOop--v0T35wCMKsWzq4h0wK_6FH9fpS439yskBI8kbf1KGIByXt4

https://www.johnnyseeds.com/vegetables/greens/pac-choi-bok-choy/joi-choi-f1-green-seed-507.html?srsltid=AfmBOop--v0T35wCMKsWzq4h0wK_6FH9fpS439yskBI8kbf1KGIByXt4

[56] [57] [58] https://university.upstartfarmers.com/blog/growing-chard-without-soil

https://university.upstartfarmers.com/blog/growing-chard-without-soil

[59] https://www.johnnyseeds.com/growers-library/vegetables/swiss-chard/swiss-chard-key-growing-information.html?srsltid=AfmBOoqzXjVRWdvnXgnS7jVDQT5Dfveo62Oeo7gUnH0USFucEh7LPTqU

https://www.johnnyseeds.com/growers-library/vegetables/swiss-chard/swiss-chard-key-growing-information.html?srsltid=AfmBOoqzXjVRWdvnXgnS7jVDQT5Dfveo62Oeo7gUnH0USFucEh7LPTqU

[60] https://zipgrow.com/a-focus-on-chard/?srsltid=AfmBOooLozW2iV_Gmh05m3z2OdmW0jCxsOqK9CipssYqi3tFTygaOafj

https://zipgrow.com/a-focus-on-chard/?srsltid=AfmBOooLozW2iV_Gmh05m3z2OdmW0jCxsOqK9CipssYqi3tFTygaOafj

[61] [62] [63] [64] [68] [69] https://extension.usu.edu/yardandgarden/research/grow-your-own-microgreens.pdf

https://extension.usu.edu/yardandgarden/research/grow-your-own-microgreens.pdf

[65] https://extension.arizona.edu/sites/extension.arizona.edu/files/attachment/Microgreens.pdf

https://extension.arizona.edu/sites/extension.arizona.edu/files/attachment/Microgreens.pdf

[66] https://paperpot.co/wp-content/uploads/2022/06/Radish-Microgreens-Paperpot-Co-Growers-Notes.pdf

https://paperpot.co/wp-content/uploads/2022/06/Radish-Microgreens-Paperpot-Co-Growers-Notes.pdf

[67] https://e-gro.org/pdf/E606.pdf

https://e-gro.org/pdf/E606.pdf

[70] https://paperpot.co/wp-content/uploads/2022/06/Pea-Shoot-Microgreens-Paperpot-Co-Growers-Notes.pdf

https://paperpot.co/wp-content/uploads/2022/06/Pea-Shoot-Microgreens-Paperpot-Co-Growers-Notes.pdf
