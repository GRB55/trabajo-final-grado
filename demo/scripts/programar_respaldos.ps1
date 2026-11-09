# Programa los respaldos (ejecutar una vez como administrador, desde la carpeta del repositorio).
# Completo: domingos 22:00 | Diferencial: lunes a sabado 22:00 | Verificacion: domingos 23:00
$repo = (Get-Location).Path
$py = "C:\Users\Gonzalo\miniconda3\envs\tfg\python.exe"
schtasks /Create /F /TN "ddjj_respaldo_completo"    /SC WEEKLY /D SUN /ST 22:00 /TR "cmd /c cd /d $repo && $py -m src.respaldo --tipo completo"
schtasks /Create /F /TN "ddjj_respaldo_diferencial" /SC WEEKLY /D MON,TUE,WED,THU,FRI,SAT /ST 22:00 /TR "cmd /c cd /d $repo && $py -m src.respaldo --tipo diferencial"
schtasks /Create /F /TN "ddjj_respaldo_verificar"   /SC WEEKLY /D SUN /ST 23:00 /TR "cmd /c cd /d $repo && $py -m src.respaldo --tipo verificar"
