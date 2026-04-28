export const initialMetrics = {
  waterTemp: 20.6,
  airHumidity: 68,
  airTemp: 23.4,
}

export const sparklineSeries = {
  waterTemp: [19.4, 19.7, 20.1, 20.8, 20.2, 20.6, 21.3, 21.8, 21.1, 21.6, 20.9, 20.3, 20.8, 21.2],
  airHumidity: [62, 65, 64, 66, 69, 71, 68, 69, 65, 67, 70, 72, 74, 75],
  airTemp: [22.1, 22.8, 23.4, 22.7, 22.2, 23.1, 24.0, 23.3, 22.5, 23.2, 24.2, 23.6, 23.1, 24.0],
}

export const ledStages = [
  { id: 'LED1', label: 'Рассвет', time: '06:00', color: '#76E7FF' },
  { id: 'LED2', label: 'Утро', time: '08:00', color: '#89F0FF' },
  { id: 'LED3', label: 'Рост', time: '10:00', color: '#9CF6DD' },
  { id: 'LED4', label: 'Вегетация', time: '11:30', color: '#C8F38E' },
  { id: 'LED5', label: 'Пик', time: '13:00', color: '#FFE66F' },
  { id: 'LED6', label: 'День', time: '14:30', color: '#FFC44B' },
  { id: 'LED7', label: 'Мягкий день', time: '16:00', color: '#FFB24B' },
  { id: 'LED8', label: 'Вечер', time: '18:00', color: '#FF9461' },
  { id: 'LED9', label: 'Закат', time: '20:00', color: '#F789D6' },
  { id: 'LED10', label: 'Ночь', time: '22:00', color: '#C5BCFF', moon: true },
]

export const initialDevices = {
  fans: { enabled: true, level: 65, title: 'Вентиляторы', subtitle: 'Скорость' },
  lights: { enabled: true, level: 80, title: 'Освещение', subtitle: 'Яркость' },
  pumps: { enabled: true, level: 70, title: 'Насосы', subtitle: 'Производит.' },
  humidifiers: { enabled: false, level: 0, title: 'Увлажнитель', subtitle: 'Влажность' },
  led: { title: 'LED лента', scenario: 'День' },
}

export const initialThoughts = [
  {
    id: 't-1',
    text: 'Температура и влажность в норме. Система работает стабильно.',
    time: '14:30',
  },
  {
    id: 't-2',
    text: 'Насосы держат поток на 70%. Для зелени это комфортный режим.',
    time: '14:31',
  },
  {
    id: 't-3',
    text: 'Если станет жарче, я мягко повышу скорость вентиляторов.',
    time: '14:32',
  },
]

export const initialMessages = [
  {
    id: 'm-1',
    from: 'assistant',
    text: 'Привет! Чат уже готов к реальной интеграции. Пока вместо маскота стоит заглушка.',
    time: '14:30',
  },
  {
    id: 'm-2',
    from: 'user',
    text: 'Какая сейчас ситуация на ферме?',
    time: '14:31',
  },
  {
    id: 'm-3',
    from: 'assistant',
    text: 'Сейчас всё в порядке: вода 20.6 °C, влажность 68%, воздух 23.4 °C. Все ключевые системы активны.',
    time: '14:31',
  },
]
