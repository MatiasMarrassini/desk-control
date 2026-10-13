# Suma la memoria y la CPU de Desk Control y de sus procesos WebView2 hijos.
# "RAM" es el Working Set (incluye páginas compartidas entre procesos, contadas varias veces);
# "privada" es la memoria propia de cada proceso, la cifra más honesta de lo que ocupa.
# Uso: powershell -ExecutionPolicy Bypass -File scripts/medir_consumo.ps1
$todos = Get-CimInstance Win32_Process
$pythons = $todos | Where-Object { $_.Name -like "python*" -and ($_.CommandLine -like "*desk_control.pyw*" -or $_.CommandLine -like "*-m widget*") }
$idsPython = $pythons | ForEach-Object { [int]$_.ProcessId }
$raiz = $pythons | Where-Object { $idsPython -notcontains [int]$_.ParentProcessId } | Select-Object -First 1
if (-not $raiz) { Write-Output "Desk Control no está corriendo."; exit 1 }
$ids = [System.Collections.Generic.List[int]]::new()
$ids.Add([int]$raiz.ProcessId)
for ($i = 0; $i -lt $ids.Count; $i++) {
    $todos | Where-Object { $_.ParentProcessId -eq $ids[$i] } | ForEach-Object { $ids.Add([int]$_.ProcessId) }
}
$antes = Get-Process -Id $ids -ErrorAction SilentlyContinue
$cpuAntes = ($antes | Measure-Object -Property CPU -Sum).Sum
Start-Sleep -Seconds 10
$despues = Get-Process -Id $ids -ErrorAction SilentlyContinue
$cpuDespues = ($despues | Measure-Object -Property CPU -Sum).Sum
$ramMB = ($despues | Measure-Object -Property WorkingSet64 -Sum).Sum / 1MB
$privadaMB = ($despues | Measure-Object -Property PrivateMemorySize64 -Sum).Sum / 1MB
$cpuPorc = ($cpuDespues - $cpuAntes) / 10 / [Environment]::ProcessorCount * 100
"Procesos: {0}   RAM: {1:N0} MB   privada: {2:N0} MB   CPU promedio (10 s): {3:N2} %" -f $despues.Count, $ramMB, $privadaMB, $cpuPorc
