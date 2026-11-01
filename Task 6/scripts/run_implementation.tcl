
# =====================================================
# STEP 1: Read project configuration from Python
# =====================================================

if {[llength $argv] < 2} {
    puts "RESULT stage=implementation status=FAILED reason=MISSING_ARGUMENTS"
    exit 1
}

set project_dir  [lindex $argv 0]
set project_name [lindex $argv 1]
set project_file [file join $project_dir build "${project_name}.xpr"]


# =====================================================
# STEP 2: Open existing Vivado project
# =====================================================

if {![file isfile $project_file]} {
    puts "RESULT stage=implementation status=FAILED reason=PROJECT_NOT_FOUND"
    exit 1
}

if {[catch {open_project $project_file} detail]} {
    puts "RESULT stage=implementation status=FAILED reason=OPEN_PROJECT_ERROR"
    puts "DETAIL: $detail"
    exit 1
}


# =====================================================
# STEP 3: Verify successful synthesis
# =====================================================

set synth_run [get_runs -quiet synth_1]

if {[llength $synth_run] == 0} {
    puts "RESULT stage=implementation status=FAILED reason=SYNTH_RUN_NOT_FOUND"
    close_project
    exit 1
}

set synth_progress [get_property PROGRESS $synth_run]
set synth_status [get_property STATUS $synth_run]
set needs_refresh [get_property NEEDS_REFRESH $synth_run]

if {$synth_progress ne "100%" ||
    ![string match "*synth_design Complete!*" $synth_status] ||
    $needs_refresh} {

    puts "RESULT stage=implementation status=FAILED reason=SYNTHESIS_NOT_READY"
    puts "SYNTH_STATUS: $synth_status"
    close_project
    exit 1
}


# =====================================================
# STEP 4: Locate implementation run and log
# =====================================================

set impl_run [get_runs -quiet impl_1]

if {[llength $impl_run] == 0} {
    puts "RESULT stage=implementation status=FAILED reason=IMPL_RUN_NOT_FOUND"
    close_project
    exit 1
}

set run_dir [get_property DIRECTORY $impl_run]
set raw_log [file normalize [file join $run_dir runme.log]]

set log_dir [file join $project_dir logs]
file mkdir $log_dir

set filtered_log [file join $log_dir impl_filtered.log]


# =====================================================
# STEP 5: Run implementation
# =====================================================

set run_error [catch {

    reset_run impl_1

    launch_runs impl_1 -to_step route_design

    wait_on_run impl_1

} detail]

set impl_progress [get_property PROGRESS $impl_run]
set impl_status [get_property STATUS $impl_run]


# =====================================================
# STEP 6: Filter implementation log
# =====================================================

set errors 0
set critical_warnings 0
set warnings 0

set log_found [file isfile $raw_log]

set output [open $filtered_log w]

if {$log_found} {

    set input [open $raw_log r]

    while {[gets $input line] >= 0} {

        if {[regexp {^\s*ERROR:} $line]} {
            incr errors
            puts $output $line

        } elseif {[regexp {^\s*CRITICAL WARNING:} $line]} {
            incr critical_warnings
            puts $output $line

        } elseif {[regexp {^\s*WARNING:} $line]} {
            incr warnings
            puts $output $line
        }
    }

    close $input
}

close $output


# =====================================================
# STEP 7: Determine implementation result
# =====================================================

if {$run_error == 0 &&
    $impl_progress eq "100%" &&
    [string match "*route_design Complete!*" $impl_status] &&
    $errors == 0 &&
    $log_found} {

    set status "SUCCESS"

} else {
    set status "FAILED"
}


# =====================================================
# STEP 8: Return summary to AI agent
# =====================================================

puts "RESULT stage=implementation status=$status errors=$errors critical_warnings=$critical_warnings warnings=$warnings log_found=$log_found"

puts "FILTERED_LOG: [file normalize $filtered_log]"

if {$run_error != 0} {
    set short_detail [string map [list "\r" " " "\n" " "] $detail]
    puts "DETAIL: [string range $short_detail 0 499]"
}


# =====================================================
# STEP 9: Close project
# =====================================================

close_project

if {$status eq "FAILED"} {
    exit 1
}

exit 0
