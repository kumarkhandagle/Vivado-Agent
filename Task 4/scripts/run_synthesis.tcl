
# =====================================================
# STEP 1: Read project configuration from Python
# =====================================================

if {[llength $argv] < 2} {
    puts "RESULT stage=synthesis status=FAILED reason=MISSING_ARGUMENTS"
    exit 1
}

set project_dir  [lindex $argv 0]
set project_name [lindex $argv 1]

set project_file "$project_dir/build/$project_name.xpr"


# =====================================================
# STEP 2: Open existing Vivado project
# =====================================================

if {![file isfile $project_file]} {
    puts "RESULT stage=synthesis status=FAILED reason=PROJECT_NOT_FOUND"
    exit 1
}

if {[catch {open_project $project_file} detail]} {
    puts "RESULT stage=synthesis status=FAILED reason=OPEN_PROJECT_ERROR"
    puts "DETAIL: $detail"
    exit 1
}


# =====================================================
# STEP 3: Locate synthesis log
# =====================================================

set run [get_runs -quiet synth_1]

if {[llength $run] == 0} {
    puts "RESULT stage=synthesis status=FAILED reason=SYNTH_RUN_NOT_FOUND"
    close_project
    exit 1
}

set run_dir [get_property DIRECTORY $run]
set log_file [file normalize [file join $run_dir runme.log]]

# Create directory for filtered log.
set report_dir [file join $project_dir logs]
file mkdir $report_dir

set filtered_log [file join $report_dir synth_filtered.log]


# =====================================================
# STEP 4: Run synthesis
# =====================================================

set run_error [catch {

    reset_run synth_1

    launch_runs synth_1

    wait_on_run synth_1

} detail]


# =====================================================
# STEP 5: Check synthesis status
# =====================================================

set progress [get_property PROGRESS $run]
set run_status [get_property STATUS $run]


# =====================================================
# STEP 6: Filter synthesis log
# =====================================================

set errors 0
set critical_warnings 0
set warnings 0

set log_found [file isfile $log_file]

set output [open $filtered_log w]

if {$log_found} {

    set input [open $log_file r]

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
# STEP 7: Determine synthesis result
# =====================================================

if {$run_error == 0 &&
    $progress eq "100%" &&
    [string match "*Complete!*" $run_status] &&
    $log_found} {

    set status "SUCCESS"

} else {
    set status "FAILED"
}


# =====================================================
# STEP 8: Return result to Python AI agent
# =====================================================

puts "RESULT stage=synthesis status=$status errors=$errors critical_warnings=$critical_warnings warnings=$warnings log_found=$log_found"

puts "FILTERED_LOG: [file normalize $filtered_log]"

if {$run_error != 0} {
    puts "DETAIL: $detail"
}


# =====================================================
# STEP 9: Close project
# =====================================================

close_project

if {$status eq "FAILED"} {
    exit 1
}

exit 0
