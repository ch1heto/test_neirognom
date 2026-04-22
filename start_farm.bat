@echo off
echo ==========================================
echo    Запуск системы "Нейроагроном"
echo ==========================================

:: 1. Запуск симулятора датчиков (работяга)
echo Запускаем симулятор ESP32...
start cmd /k "venv\Scripts\activate && python sim_esp32.py"

:: 2. Запуск мозгов системы (запись в БД и ИИ)
echo Запускаем Watchdog...
start cmd /k "venv\Scripts\activate && python watchdog.py"

:: 3. Запуск веб-сервера (мост между БД и интерфейсом)
echo Запускаем FastAPI сервер...
start cmd /k "venv\Scripts\activate && cd backend && uvicorn main:app --reload --port 8000"

:: 4. Запуск стеклянного интерфейса (React + Vite)
echo Запускаем Фронтенд...
start cmd /k "cd frontend && npm run dev"

echo ==========================================
echo Все 4 терминала запущены! 
echo Фронтенд скоро откроется по адресу http://localhost:5174/
echo ==========================================