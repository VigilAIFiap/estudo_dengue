@echo off
chcp 65001 >nul
title Vigil - inicializacao
cd /d "%~dp0"

where python >nul 2>nul || (
  echo [ERRO] Python nao encontrado. Instale em https://www.python.org e marque "Add Python to PATH".
  pause & exit /b 1
)
where node >nul 2>nul || (
  echo [ERRO] Node.js nao encontrado. Instale a versao LTS em https://nodejs.org
  pause & exit /b 1
)

echo [1/3] Instalando dependencias Python...
python -m pip install -q -r requirements.txt || (echo [ERRO] Falha no pip install. & pause & exit /b 1)

if not exist "web\node_modules" (
  echo [2/3] Instalando dependencias do frontend ^(so na primeira vez^)...
  pushd web
  call npm install || (echo [ERRO] Falha no npm install. & popd & pause & exit /b 1)
  popd
) else (
  echo [2/3] Dependencias do frontend ja instaladas.
)

echo [3/3] Abrindo a API e a interface em duas janelas...
start "Vigil API (porta 8000)" cmd /k "python -m uvicorn api.main:app --port 8000"
start "Vigil Interface (porta 3000)" cmd /k "cd /d web && npm run dev"

echo Aguardando os servidores subirem...
timeout /t 20 /nobreak >nul
start "" http://localhost:3000
echo Pronto. Para encerrar, feche as duas janelas abertas.
pause
