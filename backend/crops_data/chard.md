# CULTURE: chard

## Название

Мангольд

## Латинское название

Beta vulgaris subsp. vulgaris

## Тип культуры

leafy_greens

## Подходит для маленькой сити-фермы

yes

## Сложность

easy

## Почему подходит

Мангольд устойчив, хорошо переносит повторный срез и даёт длинный productive window. Для маленькой фермы его лучше держать в формате baby/young leaf, потому что в полном размере растение становится крупнее и заметнее затеняет соседей. [56]

## Нормы

air_temp: 18-24
humidity: 50-70
water_temp: 18-22
ph: 6.0-6.8
ec: 1.8-2.3
light_hours: 14-16
light_intensity: general: "яркое LED-освещение"

## Цикл выращивания

germination_days: 5-10
seedling_days: 10-14
harvest_days: 30-40
harvest_type: cut_and_come_again
repeat_harvest: yes

## Рекомендации по уходу

- выращивать как baby/young leaf, если пространство ограничено;

- своевременно делать срез, не допуская сильного затенения;

- не перегревать культуру;

- держать EC на среднем уровне;

- при повторных срезах следить за качеством молодых листьев.

## Типичные проблемы

- затенение соседних культур при перерастании;

- вытягивание при нехватке света;

- пожелтение при pH-дрифте;

- солевой стресс при завышенном EC;

- грубение листа при слишком длинном цикле.

## Правила алертов

### air_temp_low

condition: air_temp < 14
severity: info
message: Для мангольда прохладно, но критической проблемы нет.
advice: Если нужен быстрее рост, немного подними температуру.

### air_temp_high

condition: air_temp > 28
severity: warning
message: Для мангольда становится жарко.
advice: Усиль вентиляцию и следи за температурой раствора.

### humidity_low

condition: humidity < 40
severity: info
message: Влажность ниже желательной.
advice: Проверь тургор и испарение.

### humidity_high

condition: humidity > 75
severity: warning
message: Влажность повышена, возможны листовые проблемы.
advice: Организуй лучший воздухообмен.

### water_temp_low

condition: water_temp < 16
severity: warning
message: Раствор холоднее желаемого.
advice: Подними температуру раствора плавно.

### water_temp_high

condition: water_temp > 24
severity: warning
message: Раствор перегрет.
advice: Охлади бак и усили аэрацию.

### ph_low

condition: ph < 5.8
severity: warning
message: pH ниже рабочего диапазона.
advice: Подними pH без резких скачков.

### ph_high

condition: ph > 7.0
severity: warning
message: pH выше рабочего диапазона.
advice: Снизь pH и проконтролируй питание.

### ec_low

condition: ec < 1.6
severity: info
message: Питание слабее целевого.
advice: Подними EC небольшими шагами.

### ec_high

condition: ec > 2.5
severity: warning
message: Раствор для мангольда слишком концентрирован.
advice: Разбавь раствор и повторно измерь EC.

## Как должен отвечать AI-советник

- если всё нормально: «Мангольд в рабочем диапазоне, можно вести его как культуру повторного среза.»

- если pH низкий: «Для мангольда pH ниже нормы. Подними его плавно и проверь датчик.»

- если EC высокий: «EC у мангольда выше целевого, лучше немного разбавить раствор.»

- если температура высокая: «Мангольд терпимее части зелени, но в жаре качество листа всё равно падает.»

- если данных недостаточно: «Для оценки мангольда мне нужны температура, pH и EC.»

## Выбранные диапазоны и обоснование

По chard практические гидропонные источники расходятся по pH: встречаются как почти нейтральные, так и более классические гидропонные диапазоны. Для backend-системы выбран компромисс 6.0–6.8, а не 6.6–7.0, чтобы культура лучше совмещалась с общей логикой leafy-greens-модуля. EC 1.8–2.3 совпадает у нескольких практических источников. [57]

## Источники

- Everything You Need to Know About Growing Chard Without Soil [58]

- Swiss Chard Key Growing Information [59]

- A Focus on Chard / temperature and EC practical hydroponic ranges [60]

- Hydro hints: Nutrient film technique — Swiss chard tolerates NFT well
