# =====================================================
# STEP 1: Read project configuration from Python
# =====================================================

if {[llength $argv] < 2} {
    puts "RESULT stage=bitstream status=FAILED reason=MISSING_ARGUMENTS"
    exit 1
}

set project_dir  [lindex $argv 0]
set project_name [lindex $argv 1]
set project_file [file join $project_dir build "${project_name}.xpr"]

# =====================================================
# STEP 2: Open the existing Vivado project
# =====================================================

if {![file isfile $project_file]} {
    puts "RESULT stage=bitstream status=FAILED reason=PROJECT_NOT_FOUND"
    exit 1
}

if {[catch {open_project $project_file} detail]} {
    puts "RESULT stage=bitstream status=FAILED reason=OPEN_PROJECT_ERROR"
    puts "DETAIL: $detail"
    exit 1
}

# =====================================================
# STEP 3: Check that synthesis and routing are up to date
# =====================================================

set synth_run [get_runs -quiet synth_1]
set impl_run  [get_runs -quiet impl_1]

if {[llength $synth_run] == 0 || [llength $impl_run] == 0} {
    puts "RESULT stage=bitstream status=FAILED reason=RUN_NOT_FOUND"
    close_project
    exit 1
}

set synth_status [get_property STATUS $synth_run]
set synth_stale  [get_property NEEDS_REFRESH $synth_run]
set impl_status  [get_property STATUS $impl_run]
set impl_stale   [get_property NEEDS_REFRESH $impl_run]

if {![string match "*synth_design Complete!*" $synth_status] || $synth_stale} {
    puts "RESULT stage=bitstream status=FAILED reason=SYNTHESIS_NOT_READY"
    close_project
    exit 1
}

if {$impl_stale || !([string match "*route_design Complete!*" $impl_status] ||
                      [string match "*write_bitstream Complete!*" $impl_status])} {
    puts "RESULT stage=bitstream status=FAILED reason=IMPLEMENTATION_NOT_READY"
    close_project
    exit 1
}

# =====================================================
# STEP 4: Locate the output bitstream and log files
# =====================================================

set run_dir [get_property DIRECTORY $impl_run]
set raw_log [file join $run_dir runme.log]
set top [get_property TOP [get_filesets sources_1]]
set bit_file [file join $run_dir "${top}.bit"]

set log_dir [file join $project_dir logs]
file mkdir $log_dir
set filtered_log [file join $log_dir bitstream_filtered.log]

# =====================================================
# STEP 5: Generate bitstream from the existing implementation
# =====================================================

set run_error 0
set detail ""
set action "GENERATED"

if {[string match "*write_bitstream Complete!*" $impl_status] &&
    [file isfile $bit_file]} {
    set action "EXISTING"
} else {
    set run_error [catch {
        launch_runs impl_1 -to_step write_bitstream
        wait_on_run impl_1
    } detail]
}

# =====================================================
# STEP 6: Filter the implementation run log
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
# STEP 7: Verify that the bitstream was generated
# =====================================================

set final_status [get_property STATUS $impl_run]
set bit_found [file isfile $bit_file]

if {$run_error == 0 &&
    [string match "*write_bitstream Complete!*" $final_status] &&
    $bit_found && $log_found && $errors == 0} {
    set status "SUCCESS"
} else {
    set status "FAILED"
}

# =====================================================
# STEP 8: Return summary to Python AI agent
# =====================================================

puts "RESULT stage=bitstream status=$status action=$action errors=$errors critical_warnings=$critical_warnings warnings=$warnings bit_found=$bit_found log_found=$log_found"
puts "BIT_FILE: [file normalize $bit_file]"
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
