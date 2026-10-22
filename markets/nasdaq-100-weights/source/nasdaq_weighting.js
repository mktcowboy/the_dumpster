var dataTable = null;
var fffExists = true;
var selectedDate = null;

$(document).ready(function () {
    SetCurrentTab();

    var found = $('.filterContainer');
    if (found.length == 0) // No access message is being shown.
        return;

    var dates = $("#tradeDate").datepicker({
        changeMonth: true,
        changeYear: true,
        numberOfMonths: NUMBER_OF_MONTHS_TO_SHOW,
        showOtherMonths: true,
        selectOtherMonths: true,
        onSelect: function (selectedDate) {
            var option = this.id == "startDate" ? "minDate" : "maxDate";
            var instance = $(this).data("datepicker");
            var date = $.datepicker.parseDate(instance.settings.dateFormat || $.datepicker._defaults.dateFormat, selectedDate, instance.settings);
            dates.not(this).datepicker("option", option, date);
            UpdateExportLink();
            UpdateTable();
        }
    });

    var today = new Date();
    $("#tradeDate").datepicker("setDate", today);

    var startingTimeOfDay = $("#timeOfDay").val();

    $("#update").click(function () {
        UpdateExportLink();
        UpdateTable();
    });

    $("#resetLink").click(function (e) {
        if (e && e.preventDefault) {
            e.preventDefault();
        }
        var today = new Date();
        $("#tradeDate").datepicker("setDate", today);
        $("#timeOfDay").val(startingTimeOfDay);
        UpdateExportLink();
        UpdateTable();
        ResetToggle();
    })

    $("#timeOfDay").change(function (e) {
        if (e.target.value === "SOD" || e.target.value === "EOD") {
            UpdateExportLink();
            UpdateTable();
            ToggleTabs(false);
            ToggleHeaderTime(false);
            ToggleDatePicker(false);
        }
        if(e.target.value === "DPRO") {
            UpdateExportLink();
            ToggleTabs(true);
            GetForecastRunDateTime();
            ToggleDatePicker(true);
            DproRefreshWait();
        }
    })

    // Call the first time!
    ToggleTabs(false);
    InitializeControls();
    InitializeTable();
    UpdateTable();
    UpdateExportLink();

    $('#exportLink').click(function (event) {
        var oTable = $("#weightingsTable").dataTable();
        var timeOfDay = $("#timeOfDay").val();
        if(timeOfDay !== "DPRO"){
            if (oTable.fnSettings().fnRecordsTotal() < 1) {
                event.preventDefault();
                alert("There is nothing to export.");
            }
        }
    });

    $('#weightingsToggle').click(function (event) {
        ToggleTable();
    })
    
    $('#DproDay0').click(function () {
        StyleDproTabs(0);
    })

    $('#DproDay1').click(function () {
        StyleDproTabs(1);
    })

    $('#DproDay2').click(function () {
        StyleDproTabs(2);
    })

    $('#DproDay3').click(function () {
        StyleDproTabs(3);
    })

    $('#DproDay4').click(function () {
        StyleDproTabs(4);
    })

    $('#detailsButton, #summaryButton').click(function (event) {
        document.getElementById("weightingsToggle").click();
    })
    
    var oTable = $("#weightingsTable").dataTable();

    $('#searchBox').keyup(function () {
        oTable.fnFilter($(this).val());
    })
        
});

//-----------------------------------------------------------
// InitializeControls()
//-----------------------------------------------------------
function InitializeControls() {
    var symbol = $("#symbol").text();
    if (symbol == null)
        return;

    $("#timeOfDay").val("SOD");

    $("#timeOfDay").change(function () {
        var selection = $("#timeOfDay").val();
        if (selection == "PRO") {
            $.ajax({
                url: "/Index/ProformaAccessData",
                type: "POST",
                data: { id: symbol },
                dataType: "json",
                beforeSend: function () {
                    showSpinner();
                },
                success: function (result) {
                    if (result == null)
                        return;

                    // get the dates and update the calendar control!
                    var startDate = CreateDateObject(result.startDate);
                    var endDate = CreateDateObject(result.endDate);

                    $("#tradeDate").datepicker("setDate", (startDate.getUTCMonth() + 1) + "/" + startDate.getUTCDate() + "/" + startDate.getUTCFullYear());
                    $("#tradeDate").datepicker("option", "minDate", (startDate.getUTCMonth() + 1) + "/" + startDate.getUTCDate() + "/" + startDate.getUTCFullYear());
                    $("#tradeDate").datepicker("option", "maxDate", (endDate.getUTCMonth() + 1) + "/" + endDate.getUTCDate() + "/" + endDate.getUTCFullYear());
                    UpdateExportLink();
                    UpdateTable();
                    ToggleTabs(false);
                    ToggleHeaderTime(false);
                    ToggleDatePicker(false);
                },
                error: function (jqXHR, textStatus, errorThrown) {

                },
                complete: function () {
                    hideSpinner();
                }
            });
        }
        else {
            $("#tradeDate").datepicker("option", "minDate", null);
            $("#tradeDate").datepicker("option", "maxDate", null);
        }
    });
}


//-----------------------------------------------------------
// InitializeTable()
//-----------------------------------------------------------
function InitializeTable() {
    $("#weightingsTable").DataTable({
        "deferRender": true,
        "lengthChange": false,
        "serverSide": false,
        "pageLength": 100,
        "pagingType": "simple_numbers",
        "order": [[1, "asc"]],
        "processing": true,
        "sDom": '<"#indexTableToggle.indexTableToggle">plrtip',
        fnInitComplete: function(){
               $('div.indexTableToggle').html('<a id="summaryButton" class="selected-button button-pointer inline-block px-2 tracking-widest border rounded-full uppercase">Summary</a> <label class="switch"> <input type="checkbox"/> <span id="weightingsToggle" class="slider round"></span> </label> <a id="detailsButton" class="not-selected-button button-pointer inline-block px-2 tracking-widest border rounded-full uppercase">Detailed</a>');
                CheckForTableToggle();
        },
        "language": {
            "emptyTable": "There are no records that match your selected dates.",
            "zeroRecords": "There are no records that match your filter criteria.",
            "search": "Filter:",
            "paginate": {
                "next": '<img src="/Content/Images/Icons/blue-arrow-right.svg" alt="Next" class="inline-block ml-2 -mt-1" />',
                "previous":'<img src="/Content/Images/Icons/blue-arrow-right.svg" alt="Next" class="reverse-x inline-block ml-2 -mt-1" />'
            } 
        },
        "columns": GetColumns(),

        "drawCallback": function (settings) {
            labelTableRowNumbers("weightingsTable");
        }
    });

    $("#weightingsTable").on('page.dt', function () {
        $('html, body').animate({
            scrollTop: $("#weightingsTable_wrapper").offset().top
        }, 'fast');
    });
    
    
};

function GetColumns() {
    var arr;
    switch ($("#weightingsTable").attr("data-view")) {
        case "weightingsDefault":
            arr = GetDetailedColumns();
            break;

        case "weightingsNasdaqCommodity":
            arr = GetDetailedColumns();
            break;

        case "weightingsGreen":
            arr = GetGreenColumns();
            break;

        case "weightingsNordicFixedIncome":
            arr = GetNordicFixedIncomeColumns();
            break;

        case "weightingsUSTreasury":
            arr = GetUSTreasuryColumns();
            break;

        case "weightingsAlphaWco":
            arr = GetAlphaWcoColumns();
            break;

        case "weightingsUSTreasuryFree":
        case "weightingsFree":
            arr = GetFreeColumns();
            break;
            
        default:
            arr = GetFreeColumns();
    }

    return arr;
}


//-----------------------------------------------------------
// GetFreeColumns()
//-----------------------------------------------------------
function GetFreeColumns() {
    var columns =
    [
        {
            "targets": [0],
            "data": null,
            "orderable": false
        },
        {
            "targets": [1],
            "data": "Name",
        },
        {
            "targets": [2],
            "data": "Symbol",
        }
    ];

    return columns;
}

//-----------------------------------------------------------
// ToggleTable()
//-----------------------------------------------------------
function ToggleTable(){    
    SwitchSelectedButton();
}

function ClickedDetailButton(){
    $("#detailsButton").removeClass("not-selected-button");
    $("#detailsButton").addClass("selected-button");
    $("#summaryButton").removeClass("selected-button");
    $("#summaryButton").addClass("not-selected-button");
    ShowDetailedColumns(this.fffExists);
}

function ClickedSummaryButton(){
    $("#detailsButton").addClass("not-selected-button");
    $("#detailsButton").removeClass("selected-button");
    $("#summaryButton").addClass("selected-button");
    $("#summaryButton").removeClass("not-selected-button");
    HideDetailedColumns(this.fffExists);
}

function SwitchSelectedButton(){
    if($("#detailsButton").hasClass("selected-button")){
        ClickedSummaryButton();
    } else {
        ClickedDetailButton();
    }
}

function ResetToggle(){
    if($("#detailsButton").hasClass("selected-button")){
        document.getElementById("weightingsToggle").click();
    }
}

function HideToggle(){
    $("#indexTableToggle").hide();
}

function CheckForTableToggle() {
    var dataView = $("#weightingsTable").attr("data-view").toString();
    if(dataView === 'weightingsDefault') {
        HideDetailedColumns(this.fffExists);
    } else {
        HideToggle();
    }
    
}

function HideDetailedColumns(ShowFFFExists) {
    var table =  $("#weightingsTable").DataTable();
    table.column(7).visible(ShowFFFExists);
    table.column(8).visible(false);
    table.column(9).visible(false);
    table.column(10).visible(false);
    table.column(11).visible(false);
    table.column(12).visible(false);
}

function ShowDetailedColumns(ShowFFFExists) {
    var table =  $("#weightingsTable").DataTable();
    table.column(7).visible(ShowFFFExists);
    table.column(8).visible(true);
    table.column(9).visible(true);
    table.column(10).visible(true);
    table.column(11).visible(true);
    table.column(12).visible(true);
}

//-----------------------------------------------------------
// DproTableControls
//-----------------------------------------------------------
function ToggleTabs(show){
    if(show){
        $("#dProDatesTabs").show();
    } else {
        $("#dProDatesTabs").hide();
    }
}

//-----------------------------------------------------------
// Time Header Toggle
//-----------------------------------------------------------
function ToggleHeaderTime(show) {
    if (show) {
        $("#sodEodTime").hide();
        $("#dproTime").show();
    } else {
        $("#sodEodTime").show();
        $("#dproTime").hide();
    }
}

function DproUpdateTable(date) {
    UpdateTableDproDate(date);
}

function GetForecastRunDateTime() {
    var symbol = $("#symbol").text();
    if (symbol == null)
        return;

    $.ajax({
        url: "/Index/GetForecastRunDateTime",
        type: "POST",
        data: { symbol: symbol },
        dataType: "json",
        beforeSend: function () {
            showSpinner();
        },
        success: function (result) {
            if (result == null)
                return;

            var lastUpdateTimeDate = result.lastUpdateDateTime;

            console.log(result);

            $("#dproTime > time").text(lastUpdateTimeDate);
            ToggleHeaderTime(true);
            
        },
        error: function (jqXHR, textStatus, errorThrown) {
            console.log(`Unable to retrieve forecast run datetime. Status: ${textStatus}. Error: ${errorThrown}`)
            ToggleHeaderTime(false);
        },
        complete: function () {
            hideSpinner();
        }
    });
}

function StyleDproTabs(tabNumber){
    SetAllTabsToNotSelected();
    switch (tabNumber){
        case 0:
            $(DproDay0).addClass("selected-tab");
            break;
        case 1:
            $(DproDay1).addClass("selected-tab");
            break;
        case 2:
            $(DproDay2).addClass("selected-tab");
            break;
        case 3:
            $(DproDay3).addClass("selected-tab");
            break;
        case 4:
            $(DproDay4).addClass("selected-tab");
            break;
    }
}

function SetAllTabsToNotSelected()
{
    $(DproDay0).removeClass("selected-tab");
    $(DproDay1).removeClass("selected-tab");
    $(DproDay2).removeClass("selected-tab");
    $(DproDay3).removeClass("selected-tab");
    $(DproDay4).removeClass("selected-tab");
}

function CheckForFreeFloatFactor(weightingList) {
    var result = false;
    weightingList.forEach((weight) => {
        if(weight.FreeFloatFactor){
            result = true;
        }
    })
    return result;
}




function ToggleFFFVisibility(toggle) {
    if(toggle !== undefined) {
        var table = $("#weightingsTable").DataTable();
        if (table.context[0].aoColumns.length > 7) {
            table.column(7).visible(toggle);
        }
        
    }
}

function DproRefreshWait() {
    $("#DproDay0").click();
    StyleDproTabs(0);
}

function ToggleDatePicker(hidePicker){
    if(hidePicker){
        var today = new Date();
        $("#tradeDate").datepicker("setDate", today);
    }
    $("#tradeDate").datepicker("option", "disabled", hidePicker);
}


//-----------------------------------------------------------
// GetDefaultColumns()
//-----------------------------------------------------------
function GetDefaultColumns() {
    var columns =
    [
        {
            "targets": 0,
            "data": null,
            "orderable": false,
        },
        {
            "targets": [1],
            "data": "Name",
        },
        {
            "targets": [2],
            "data": "Symbol",
        },
        {
            "targets": [3],
            "data": "T1AdjustedClose",
            "type": "num",
            "render": $.fn.dataTable.render.number(',', '.', 2),
        },
        {
            "targets": [4],
            "data": "NumberOfShares",
            "render": $.fn.dataTable.render.number(',', '.'),
        },
        {
            "targets": [5],
            "data": "SecurityMktValue",
            "type": "num",
            "render": $.fn.dataTable.render.number(',', '.'),
        },
        {
            "targets": [6],
            "data": "SecurityWeightingPct",
            "type": "num",
            "render": $.fn.dataTable.render.number(',', '.', 2),
        }
    ];

    return columns;
}


//-----------------------------------------------------------
// GetGreenColumns()
//-----------------------------------------------------------
function GetGreenColumns() {
    var columns =
    [
        {
            "targets": [0],
            "data": null, "orderable": false
        },
        {
            "targets": [1],
            "data": "Name",
        },
        {
            "targets": [2],
            "data": "SEDOL",
        },
        {
            "targets": [3],
            "data": "Symbol",
        },
        {
            "targets": [4],
            "data": "MIC",
        },
        {
            "targets": [5],
            "data": "T1AdjustedClose",
            "type": "num",
            "render": $.fn.dataTable.render.number(',', '.', 2),
        },
        {
            "targets": [6],
            "data": "Currency",
        },
        {
            "targets": [7],
            "data": "SpotRate",
            "type": "num",
            "render": $.fn.dataTable.render.number(',', '.', 2),
        },
        {
            "targets": [8],
            "data": "NumberOfShares",
            "type": "num",
            "render": $.fn.dataTable.render.number(',', '.', 0),
        },
        {
            "targets": [9],
            "data": "SecurityMktValue",
            "type": "num",
            "render": $.fn.dataTable.render.number(',', '.', 2),
        },
        {
            "targets": [10],
            "data": "SecurityWeightingPct",
            "type": "num",
            "render": $.fn.dataTable.render.number(',', '.', 2),
        }
        
    ];

    return columns;
}


//-----------------------------------------------------------
// GetNordicFixedIncomeColumns()
//-----------------------------------------------------------
function GetNordicFixedIncomeColumns() {
    var columns =
    [
        {
            "targets": [0],
            "data": null,
            "orderable": false
        },
        {
            "targets": [1],
            "data": "Symbol",
        },
        {
            "targets": [2],
            "data": "ISIN",
        },
        {
            "targets": [3],
            "data": "NumberOfShares",
            "type": "num",
            "render": $.fn.dataTable.render.number(',', '.', 0),
        },
        {
            "targets": [4],
            "data": "Yield",
            "type": "num",
            "render": $.fn.dataTable.render.number(',', '.', 2),
        },
        {
            "targets": [5],
            "data": "T1AdjustedClose",
            "type": "num",
            "render": $.fn.dataTable.render.number(',', '.', 2),
        },
        {
            "targets": [6],
            "data": "AccruedInterest",
            "type": "num",
            "render": $.fn.dataTable.render.number(',', '.', 2),
        },
        {
            "targets": [7],
            "data": "Duration",
            "type": "num",
            "render": $.fn.dataTable.render.number(',', '.', 2),
        },
        {
            "targets": [8],
            "data": "SecurityMktValue",
            "type": "num",
            "render": $.fn.dataTable.render.number(',', '.', 0),
        },
        {
            "targets": [9],
            "data": "SecurityWeightingPct",
            "type": "num",
            "render": $.fn.dataTable.render.number(',', '.', 2),
        }
    ];

    return columns;
}



//-----------------------------------------------------------
// GetAlphaWcoColumns()
//-----------------------------------------------------------
function GetAlphaWcoColumns() {
    var columns =
    [
        {
            "targets": [0],
            "data": null,
            "orderable": false,
        },
        {
            "targets": [1],
            "data": "Name",
        },
        {
            "targets": [2],
            "data": "Symbol",
        },
        {
            "targets": [3],
            "data": "T1AdjustedClose",
            "type": "num",
            "render": $.fn.dataTable.render.number(',', '.', 2),
        }
    ];

    return columns;
}


//-----------------------------------------------------------
// UpdateTable()
//-----------------------------------------------------------
function UpdateTable() {
        let showFFF;
        var symbol = $("#symbol").text();
        if (symbol == null)
            return;

        var tradeDate = $("#tradeDate").datepicker("getDate");
        if (tradeDate == null)
            return;

        var oTable = $("#weightingsTable").dataTable();
        oTable.fnClearTable();

        showSpinner();

        $.ajax({
            url: "/Index/WeightingData",
            type: "POST",
            data: { id: symbol, tradeDate: tradeDate.toISONonUtcString(), timeOfDay: $("#timeOfDay").val() },
            dataType: "json",
            beforeSend: function () {
                $(".dataTables_empty").text("Loading data.");
                showSpinner();
            },
            success: function (result) {
                if (!result.aaData || !result.aaData.length) {
                    return;
                }
                showFFF=CheckForFreeFloatFactor(result.aaData);
                UpdateFFFExists(showFFF);
                oTable.fnAddData(result.aaData);
            },
            error: function (jqXHR, textStatus, errorThrown) {
                if (jqXHR.readyState == 0 && jqXHR.status == 0 && jqXHR.statusText == "abort") {
                    return;
                }
                else {
                    if (jqXHR.responseText.indexOf("maxJsonLength") > 0)
                        $(".dataTables_empty").text("There is too much data to display.");
                }
            },
            complete: function () {
                ToggleFFFVisibility(showFFF);
                hideSpinner();
                $(".dataTables_empty").text("There are no records that match your selected dates.");
            }
        });
}

function UpdateTableDproDate(dproDate) {
    if (selectedDate) {
        if (dproDate == selectedDate) {
            return;
        }
    }
    selectedDate = dproDate;
    let showFFF;
    var symbol = $("#symbol").text();
    if (symbol == null)
        return;

    var oTable = $("#weightingsTable").dataTable();
    oTable.fnClearTable();
    
    showSpinner();

    $.ajax({
        url: "/Index/WeightingData",
        type: "POST",
        data: { id: symbol, tradeDate: dproDate, timeOfDay: $("#timeOfDay").val() },
        dataType: "json",
        beforeSend: function () {
            showSpinner();
        },
        success: function (result) {
            if (!result.aaData || !result.aaData.length) {
                return;
            }
            showFFF = CheckForFreeFloatFactor(result.aaData);
            UpdateFFFExists(showFFF);
            oTable.fnAddData(result.aaData);
        },
        error: function (jqXHR, textStatus, errorThrown) {
            if (jqXHR.readyState == 0 && jqXHR.status == 0 && jqXHR.statusText == "abort") {
                return;
            }
            else {
                if (jqXHR.responseText.indexOf("maxJsonLength") > 0)
                    $(".dataTables_empty").text("There is too much data to display.");
            }
        },
        complete: function () {
            ToggleFFFVisibility(showFFF);
            hideSpinner();
        }
    });
}

function UpdateFFFExists(newValue){
    fffExists = newValue;
}

//-----------------------------------------------------------
// UpdateExportLink()
//-----------------------------------------------------------
function UpdateExportLink() {
    var tradeDate = $("#tradeDate").datepicker("getDate");

    if (tradeDate != undefined) {
        var href = "/Index/ExportWeightings/" + $("#symbol").text() + "?tradeDate=" + tradeDate.toISONonUtcString() + "&timeOfDay=" + $("#timeOfDay").val();
        $("#exportLink").attr("href", href);
    }
}


//-----------------------------------------------------------
// labelTableRowNumbers(tableName)
//-----------------------------------------------------------
function labelTableRowNumbers(tableName) {
    if (typeof tableName != "undefined") {
        var table_rows = $("#" + tableName).dataTable().fnGetNodes();
        $.each(table_rows, function (index) {
            $("td:first", this).html(index + 1);
        });
    }
}


function CreateDateObject(datetime) {
    if (datetime == undefined)
        return null;

    return new Date(parseInt(datetime.replace(/\/Date\((\d+)\)\//gi, "$1")));
}


//-----------------------------------------------------------
// GetDetailedColumns()
//-----------------------------------------------------------
function GetDetailedColumns() {
    var columns =
        [
            {
                "targets": 0,
                "data": null,
                "orderable": false,
            },
            {
                "targets": [1],
                "data": "Name",
            },
            {
                "targets": [2],
                "data": "Symbol",
            },
            {
                "targets": [3],
                "data": "T1AdjustedClose",
                "type": "num",
                "render": $.fn.dataTable.render.number(',', '.', 2)
            },
            {
                "targets": [4],
                "data": "NumberOfShares",
                "render": $.fn.dataTable.render.number(',', '.')
            },
            {
                "targets": [5],
                "data": "SecurityMktValue",
                "type": "num",
                "render": $.fn.dataTable.render.number(',', '.')
            },
            {
                "targets": [6],
                "data": "SecurityWeightingPct",
                "type": "num",
                "render": $.fn.dataTable.render.number(',', '.', 2)
            },
            {
                "targets": [7],
                "data": "FreeFloatFactor",
                "type": "num",
                "render": $.fn.dataTable.render.number(',', '.', 2)
            },
            {
                "targets": [8],
                "data": "SpotRate",
                // "width": "80px",
                "type": "num",
                "render": $.fn.dataTable.render.number(',', '.', 2)
            },
            {
                "targets": [9],
                "data": "ISIN"
            },
            {
                "targets": [10],
                "data": "SEDOL"
            },
            {
                "targets": [11],
                "data": "IndustryCode8"
            },
            {
                "targets": [12],
                "data": "SecurityDividendMktValue",
                "render": $.fn.dataTable.render.number(',', '.'),
            }
        ];

    return columns;
}


//-----------------------------------------------------------
// AddDays To Date()
//-----------------------------------------------------------
Date.prototype.addDays = function (days) {
    var date = new Date(this.valueOf());
    date.setDate(date.getDate() + days);
    return date;
}