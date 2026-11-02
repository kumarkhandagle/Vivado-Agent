
# =====================================================
# STEP 1: Read project configuration from Python
# =====================================================

if {[llength $argv] < 2} {
    puts "RESULT status=ERROR passed=-1 failed=-1 coverage=NA failed_ids=none"
    puts "SIM_ERROR reason=\"Expected arguments: project_dir project_name\""
    exit 1
}

set project_dir  [lindex $argv 0]
set project_name [lindex $argv 1]

set project_file "$project_dir/build/$project_name.xpr"
set sim_log "$project_dir/build/$project_name.sim/sim_1/behav/xsim/simulate.log"

# Expected number of directed tests
set expected_tests 7

# Limit error details sent to AI agent
set max_reasons_per_test 3
set max_reason_chars 500


# =====================================================
# Helper: Format error message for single-line output
# =====================================================

proc format_reason {reason max_chars} {

    set reason [string map [list \
        "\r" " " \
        "\n" " " \
        "\t" " " \
        "\\" "\\\\" \
        "\"" "\\\"" \
    ] $reason]

    if {[string length $reason] > $max_chars} {
        set reason "[string range $reason 0 [expr {$max_chars - 4}]]..."
    }

    return $reason
}


# =====================================================
# STEP 2: Open Vivado project
# =====================================================

if {![file isfile $project_file]} {

    puts "RESULT status=ERROR passed=-1 failed=-1 coverage=NA failed_ids=none"
    puts "SIM_ERROR reason=\"Vivado project file not found\""

    exit 1
}

open_project $project_file


# =====================================================
# STEP 3: Configure behavioral simulation
# =====================================================

set_property target_simulator XSim [current_project]

set sim_fileset [get_filesets sim_1]

set_property top tb_top $sim_fileset

set_property xsim.simulate.runtime {} $sim_fileset

update_compile_order -fileset sim_1


# =====================================================
# STEP 4: Delete previous simulation log
# =====================================================

if {[file exists $sim_log]} {
    file delete $sim_log
}


# =====================================================
# STEP 5: Run behavioral simulation
# =====================================================

set result [catch {

    launch_simulation -simset sim_1 -mode behavioral

    run -all

} error_message]

# Close simulator
catch {close_sim}

# Check simulation execution
if {$result != 0} {

    puts "RESULT status=ERROR passed=-1 failed=-1 coverage=NA failed_ids=none"

    puts "SIM_ERROR reason=\"[format_reason $error_message $max_reason_chars]\""

    puts "SIM_LOG: $sim_log"

    close_project
    exit 1
}


# =====================================================
# STEP 6: Initialize simulation results
# =====================================================

set passed -1
set failed -1
set coverage "NA"
set status "INCOMPLETE"

set failed_ids {}
set failed_test_details {}
set pending_errors {}


# =====================================================
# STEP 7: Read and analyze simulation log
# =====================================================

if {[file isfile $sim_log]} {

    set file [open $sim_log r]

    set log_text [read $file]

    close $file


    # ---------------------------------------------
    # Extract overall test summary
    # ---------------------------------------------

    regexp {TESTS_PASSED:[[:space:]]*([0-9]+)} \
        $log_text -> passed

    regexp {TESTS_FAILED:[[:space:]]*([0-9]+)} \
        $log_text -> failed

    regexp {COVERAGE:[[:space:]]*([0-9]+)%} \
        $log_text -> coverage


    # ---------------------------------------------
    # Extract failed test IDs and reasons
    # ---------------------------------------------

    foreach line [split $log_text "\n"] {

        set line [string trim $line]


        # Capture ERROR messages printed by testbench
        if {[regexp {(^|[[:space:]])ERROR:[[:space:]]*(.+)$} \
                $line -> unused error_text]} {

            lappend pending_errors [string trim $error_text]
        }


        # Detect individual test results
        if {[regexp {ST_([0-9]+):[[:space:]]*(PASS|FAIL)} \
                $line -> number test_status]} {

            if {$test_status eq "FAIL"} {

                set test_id "ST_$number"

                lappend failed_ids $test_id


                # Determine failure reason
                if {[llength $pending_errors] == 0} {

                    set reason "No ERROR detail was printed for this failing test"

                } else {

                    set selected [lrange $pending_errors 0 \
                        [expr {$max_reasons_per_test - 1}]]

                    set reason [join $selected " | "]

                    set omitted [expr {
                        [llength $pending_errors] - [llength $selected]
                    }]

                    if {$omitted > 0} {
                        append reason " | ($omitted additional errors omitted)"
                    }
                }


                # Store failed test ID with reason
                lappend failed_test_details \
                    [list $test_id $reason]
            }


            # Clear errors for next test case
            set pending_errors {}
        }
    }


    # ---------------------------------------------
    # Determine overall simulation status
    # ---------------------------------------------

    if {$passed >= 0 &&
        $failed >= 0 &&
        $coverage ne "NA"} {

        set status "FAIL"

        if {$passed == $expected_tests &&
            $failed == 0 &&
            $coverage == 100 &&
            [llength $failed_ids] == 0 &&
            [string first "ALL TESTS PASSED" $log_text] != -1} {

            set status "PASS"
        }
    }
}


# =====================================================
# STEP 8: Return results to Python AI agent
# =====================================================

# Convert failed test IDs into comma-separated string
set failed_ids_value "none"

if {[llength $failed_ids] > 0} {
    set failed_ids_value [join $failed_ids ","]
}


# Print overall results
puts "RESULT status=$status passed=$passed failed=$failed coverage=$coverage failed_ids=$failed_ids_value"


# Print each failed test and reason
foreach detail $failed_test_details {

    lassign $detail test_id reason

    puts "FAILED_TEST id=$test_id reason=\"[format_reason $reason $max_reason_chars]\""
}


# Warn if test counts do not match individual markers
if {$failed > [llength $failed_test_details]} {

    puts "WARNING: TESTS_FAILED=$failed but only [llength $failed_test_details] individual FAIL markers were found"
}


# Return simulation log location
puts "SIM_LOG: $sim_log"


# =====================================================
# STEP 9: Close project
# =====================================================

close_project

exit 0
