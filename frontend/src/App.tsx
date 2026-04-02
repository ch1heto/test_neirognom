import { useEffect, useState } from 'react'
import mqtt from 'mqtt'

const SENSOR_TOPIC = 'farm/tray_1/sensors'
const MQTT_WS_URL = 'ws://31.56.208.196:9001'
const API_URL = 'http://31.56.208.196:8000/api/device/control'

function App() {
  const [temperature, setTemperature] = useState<number | null>(null)
  const [requestState, setRequestState] = useState('Готово к управлению вентилятором')

  useEffect(() => {
    const client = mqtt.connect(MQTT_WS_URL)

    client.on('connect', () => {
      client.subscribe(SENSOR_TOPIC)
    })

    client.on('message', (topic, message) => {
      if (topic !== SENSOR_TOPIC) {
        return
      }

      try {
        const data = JSON.parse(message.toString()) as { temperature?: number }

        if (typeof data.temperature === 'number') {
          setTemperature(data.temperature)
        }
      } catch (error) {
        console.error('Не удалось обработать MQTT-сообщение', error)
      }
    })

    client.on('error', (error) => {
      console.error('Ошибка MQTT-подключения', error)
    })

    return () => {
      client.end(true)
    }
  }, [])

  const sendFanCommand = async (state: 'ON' | 'OFF') => {
    setRequestState(`Отправка команды ${state}...`)

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          target_id: 'tray_1',
          device_type: 'fan',
          state,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      setRequestState(`Команда ${state} отправлена`)
    } catch (error) {
      console.error('Не удалось отправить команду вентилятору', error)
      setRequestState(`Ошибка отправки команды ${state}`)
    }
  }

  return (
    <main className="dashboard">
      <section className="dashboard__panel">
        <p className="dashboard__eyebrow">Neuroagronom Control</p>
        <h1>Панель управления Neuroagronom</h1>

        <div
          style={{
            marginBottom: '24px',
            padding: '34px 28px',
            borderRadius: '26px',
            background:
              'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(228,242,255,0.96) 100%)',
            border: '1px solid rgba(133, 168, 201, 0.28)',
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.7), 0 18px 40px rgba(31, 73, 120, 0.12)',
          }}
        >
          <div
            style={{
              fontSize: 'clamp(1.7rem, 4vw, 3rem)',
              fontWeight: 800,
              lineHeight: 1.15,
              color: '#12385a',
            }}
          >
            {temperature === null ? 'Ожидание данных...' : `🌡️ Температура: ${temperature} °C`}
          </div>
        </div>

        <div
          style={{
            display: 'grid',
            gap: '14px',
          }}
        >
          <button
            className="dashboard__button"
            style={{
              background: 'linear-gradient(135deg, #1d6f42 0%, #2f8f73 100%)',
              boxShadow: '0 18px 30px rgba(29, 111, 66, 0.28)',
            }}
            onClick={() => sendFanCommand('ON')}
          >
            Включить вентилятор (ON)
          </button>

          <button
            className="dashboard__button"
            style={{
              background: 'linear-gradient(135deg, #a72d2d 0%, #d94e4e 100%)',
              boxShadow: '0 18px 30px rgba(167, 45, 45, 0.26)',
            }}
            onClick={() => sendFanCommand('OFF')}
          >
            Выключить вентилятор (OFF)
          </button>
        </div>

        <p className="dashboard__status">{requestState}</p>
      </section>
    </main>
  )
}

export default App
