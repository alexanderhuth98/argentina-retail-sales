param(
    [string]$DesktopBin,
    [switch]$SkipTom
)

if ($env:PBIP_SKIP_TOM -eq "1") { $SkipTom = $true }

$ErrorActionPreference = "Stop"
$powerBiRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Join-Path (Get-Location).Path "powerbi" }
$projectRoot = Split-Path -Parent $powerBiRoot
$dataRoot = Join-Path $projectRoot "portfolio_data"
$modelPath = Join-Path $powerBiRoot "ArgentinaRetail.SemanticModel\model.bim"
$pagesRoot = Join-Path $powerBiRoot "ArgentinaRetail.Report\definition\pages"
$sourceContracts = @{
    "monthly_summary" = "monthly_summary.csv"
    "payment_mix" = "payment_mix.csv"
    "category_mix" = "category_mix.csv"
    "channel_mix" = "channel_mix.csv"
    "quality_checks" = "quality_checks.csv"
}

$jsonFiles = New-Object System.Collections.Generic.List[string]
[System.IO.Directory]::EnumerateFiles($powerBiRoot, "*.json", [System.IO.SearchOption]::AllDirectories) |
    ForEach-Object { $jsonFiles.Add($_) }
@(
    (Join-Path $powerBiRoot "ArgentinaRetail.pbip"),
    (Join-Path $powerBiRoot "ArgentinaRetail.Report\.platform"),
    (Join-Path $powerBiRoot "ArgentinaRetail.Report\definition.pbir"),
    (Join-Path $powerBiRoot "ArgentinaRetail.SemanticModel\.platform"),
    (Join-Path $powerBiRoot "ArgentinaRetail.SemanticModel\definition.pbism"),
    $modelPath
) | ForEach-Object { $jsonFiles.Add($_) }

foreach ($path in $jsonFiles) {
    $null = [System.IO.File]::ReadAllText($path) | ConvertFrom-Json -ErrorAction Stop
}

$modelText = [System.IO.File]::ReadAllText($modelPath)
if ([regex]::IsMatch($modelText, '(?i)[A-Z]:\\|/Users/|/home/')) {
    throw "model.bim contiene una ruta absoluta o personal."
}
if ([regex]::IsMatch($modelText, '(?i)password\s*=|pwd\s*=|user\s*id\s*=|uid\s*=')) {
    throw "model.bim contiene una credencial embebida."
}

$modelDefinition = $modelText | ConvertFrom-Json
$parameters = @{}
foreach ($expression in $modelDefinition.model.expressions) {
    $parameters[$expression.name] = $expression.expression
}
if (-not $parameters.ContainsKey("ServerName") -or -not $parameters.ContainsKey("DatabaseName")) {
    throw "Faltan los parametros ServerName o DatabaseName."
}
if (-not $parameters["ServerName"].Contains("IsParameterQuery=true") -or
    -not $parameters["DatabaseName"].Contains("IsParameterQuery=true")) {
    throw "Los parametros de conexion no estan declarados como parametros M."
}

$modelTables = @{}
foreach ($table in $modelDefinition.model.tables) {
    $columns = @{}
    foreach ($column in $table.columns) { $columns[$column.name] = $true }
    $measures = @{}
    foreach ($measure in $table.measures) { $measures[$measure.name] = $true }
    $modelTables[$table.name] = @{ Columns = $columns; Measures = $measures }
}

@("monthly_summary", "payment_mix", "category_mix", "channel_mix", "quality_checks",
  "Calendario", "Formato", "MedioPago", "Categoria", "Canal", "Medidas") |
    ForEach-Object {
        if (-not $modelTables.ContainsKey($_)) { throw "Falta la tabla requerida: $_" }
    }

$rowCounts = @{}
foreach ($tableName in $sourceContracts.Keys) {
    $csvPath = Join-Path $dataRoot $sourceContracts[$tableName]
    if (-not (Test-Path -LiteralPath $csvPath)) { throw "Falta la fuente requerida: $csvPath" }
    $records = @(Import-Csv -LiteralPath $csvPath -Encoding UTF8)
    if ($records.Count -eq 0) { throw "La fuente no contiene filas: $csvPath" }
    $rowCounts[$tableName] = $records.Count
    $csvColumns = @($records[0].PSObject.Properties.Name)
    $tableDefinition = @($modelDefinition.model.tables | Where-Object { $_.name -eq $tableName })[0]
    $missing = @($tableDefinition.columns.sourceColumn | Where-Object { $_ -notin $csvColumns })
    if ($missing.Count -gt 0) { throw "Columnas ausentes en ${csvPath}: $($missing -join ', ')" }

    foreach ($column in $tableDefinition.columns) {
        if ($column.dataType -eq "string") { continue }
        for ($rowIndex = 0; $rowIndex -lt $records.Count; $rowIndex++) {
            $value = [string]$records[$rowIndex].PSObject.Properties[$column.sourceColumn].Value
            if ([string]::IsNullOrWhiteSpace($value)) { continue }
            $isValid = $false
            if ($column.dataType -eq "int64") {
                $parsedInteger = 0L
                $isValid = [long]::TryParse($value, [System.Globalization.NumberStyles]::Integer,
                    [System.Globalization.CultureInfo]::InvariantCulture, [ref]$parsedInteger)
            } elseif ($column.dataType -eq "double") {
                $parsedDouble = 0.0
                $isValid = [double]::TryParse($value, [System.Globalization.NumberStyles]::Float,
                    [System.Globalization.CultureInfo]::InvariantCulture, [ref]$parsedDouble)
            } elseif ($column.dataType -eq "dateTime") {
                $parsedDate = [datetime]::MinValue
                $isValid = [datetime]::TryParseExact($value, "yyyy-MM-dd",
                    [System.Globalization.CultureInfo]::InvariantCulture,
                    [System.Globalization.DateTimeStyles]::None, [ref]$parsedDate)
            } elseif ($column.dataType -eq "boolean") {
                $parsedBoolean = $false
                $isValid = [bool]::TryParse($value, [ref]$parsedBoolean)
            }
            if (-not $isValid) {
                throw "Tipo invalido en $tableName.$($column.sourceColumn), fila $($rowIndex + 2): $value"
            }
        }
    }
}

$highFailures = @(Import-Csv -LiteralPath (Join-Path $dataRoot "quality_checks.csv") -Encoding UTF8 |
    Where-Object { $_.severity -eq "HIGH" -and $_.status -ne "PASS" })
if ($highFailures.Count -gt 0) { throw "Los CSV no superan el gate HIGH." }

$visualFiles = @([System.IO.Directory]::EnumerateFiles(
    $pagesRoot, "visual.json", [System.IO.SearchOption]::AllDirectories
))
foreach ($path in $visualFiles) {
    $text = [System.IO.File]::ReadAllText($path)
    foreach ($match in [regex]::Matches($text, '"queryRef":"([^"]+)"')) {
        $reference = $match.Groups[1].Value
        $separator = $reference.IndexOf(".")
        if ($separator -lt 1) { continue }
        $entity = $reference.Substring(0, $separator)
        $property = $reference.Substring($separator + 1)
        if (-not $modelTables.ContainsKey($entity)) { throw "Visual con tabla inexistente: $reference" }
        if (-not $modelTables[$entity].Columns.ContainsKey($property) -and
            -not $modelTables[$entity].Measures.ContainsKey($property)) {
            throw "Visual con campo inexistente: $reference"
        }
    }
}

$pageFiles = @([System.IO.Directory]::EnumerateFiles(
    $pagesRoot, "page.json", [System.IO.SearchOption]::AllDirectories
))
$expectedPages = @("Panorama ejecutivo", "Medios de pago", "Categorias", "Canales y calidad")
$pageNames = @($pageFiles | ForEach-Object {
    ([System.IO.File]::ReadAllText($_) | ConvertFrom-Json).displayName
})
if (@($expectedPages | Where-Object { $_ -notin $pageNames }).Count -gt 0) {
    throw "No se encontraron las cuatro paginas requeridas."
}
foreach ($pageFile in $pageFiles) {
    $pageRoot = Split-Path -Parent $pageFile
    $pageVisuals = @([System.IO.Directory]::EnumerateFiles(
        (Join-Path $pageRoot "visuals"), "visual.json", [System.IO.SearchOption]::AllDirectories
    ) | ForEach-Object { [System.IO.File]::ReadAllText($_) | ConvertFrom-Json })
    if ($pageVisuals.Count -lt 8) { throw "La pagina $pageRoot tiene menos de ocho visuales." }
    $cards = @($pageVisuals | Where-Object { $_.visual.visualType -eq "card" })
    if ($cards.Count -lt 4) { throw "La pagina $pageRoot no tiene cuatro KPI superiores." }
    if (@($cards | Where-Object { $_.position.y -ge 210 }).Count -gt 0) {
        throw "La pagina $pageRoot no conserva los KPI en la franja superior."
    }
}

if (-not $SkipTom) {
    if (-not $DesktopBin) {
        $candidates = New-Object System.Collections.Generic.List[string]
        $candidates.Add((Join-Path $env:ProgramFiles "Microsoft Power BI Desktop\bin"))
        $desktopPackage = Get-AppxPackage -Name "Microsoft.MicrosoftPowerBIDesktop" -ErrorAction SilentlyContinue |
            Sort-Object Version -Descending | Select-Object -First 1
        if ($desktopPackage) { $candidates.Add((Join-Path $desktopPackage.InstallLocation "bin")) }
        foreach ($candidate in $candidates) {
            if ((Test-Path -LiteralPath (Join-Path $candidate "Microsoft.AnalysisServices.Server.Core.dll")) -and
                (Test-Path -LiteralPath (Join-Path $candidate "Microsoft.AnalysisServices.Server.Tabular.dll"))) {
                $DesktopBin = $candidate
                break
            }
        }
    }
    if (-not $DesktopBin) { throw "No se encontro Power BI Desktop; use -SkipTom para validacion estructural." }
    Add-Type -Path (Join-Path $DesktopBin "Microsoft.AnalysisServices.Server.Core.dll")
    Add-Type -Path (Join-Path $DesktopBin "Microsoft.AnalysisServices.Server.Tabular.dll")
    $database = [Microsoft.AnalysisServices.Tabular.JsonSerializer]::DeserializeDatabase($modelText)
    $tomSummary = "$($database.Model.Tables.Count) tablas TOM, $($database.Model.Relationships.Count) relaciones TOM"
} else {
    $tomSummary = "TOM omitido explicitamente"
}

$measureCount = 0
foreach ($table in $modelDefinition.model.tables) {
    foreach ($measure in $table.measures) { $measureCount += 1 }
}
Write-Output "PBIP validado."
Write-Output "JSON: $($jsonFiles.Count) archivos. Modelo: $($modelTables.Count) tablas, $($modelDefinition.model.relationships.Count) relaciones, $measureCount medidas; $tomSummary."
Write-Output "Reporte: $($pageFiles.Count) paginas, $($visualFiles.Count) visuales."
Write-Output "CSV: $(($sourceContracts.Keys | Sort-Object | ForEach-Object { $_ + '=' + $rowCounts[$_] }) -join '; ')."
