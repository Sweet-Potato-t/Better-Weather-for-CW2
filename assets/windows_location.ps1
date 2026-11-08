$ErrorActionPreference = 'Stop'
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Devices.Geolocation.Geolocator, Windows.Devices.Geolocation, ContentType = WindowsRuntime]
    $null = [Windows.Devices.Geolocation.Geoposition, Windows.Devices.Geolocation, ContentType = WindowsRuntime]

    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]

    function Await-WinRt($operation, $resultType) {
        $asTask = $asTaskGeneric.MakeGenericMethod($resultType)
        $task = $asTask.Invoke($null, @($operation))
        if (-not $task.Wait(15000)) {
            throw '定位请求超时'
        }
        return $task.Result
    }

    $access = Await-WinRt ([Windows.Devices.Geolocation.Geolocator]::RequestAccessAsync()) ([Windows.Devices.Geolocation.GeolocationAccessStatus])
    if ($access -ne [Windows.Devices.Geolocation.GeolocationAccessStatus]::Allowed) {
        throw "定位权限未授予 ($access)"
    }

    $locator = [Windows.Devices.Geolocation.Geolocator]::new()
    $locator.DesiredAccuracy = [Windows.Devices.Geolocation.PositionAccuracy]::High
    $position = Await-WinRt ($locator.GetGeopositionAsync()) ([Windows.Devices.Geolocation.Geoposition])
    $point = $position.Coordinate.Point.Position
    Write-Output ("OK {0:R} {1:R} {2:R}" -f $point.Latitude, $point.Longitude, $position.Coordinate.Accuracy)
}
catch {
    Write-Output ("ERR " + $_.Exception.Message)
}
