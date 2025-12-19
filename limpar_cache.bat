@echo off
echo Removendo pastas __pycache__...
for /d /r %%d in (__pycache__) do (
    if exist "%%d" (
        echo Removendo: %%d
        rd /s /q "%%d"
    )
)
echo.
echo Limpeza concluida!
pause
