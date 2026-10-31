
# =====================================================
# STEP 1: Define project paths
# =====================================================

set project_dir  "C:/Agents/Day7"
set project_name "fpga_demo"

set project_file "$project_dir/build/$project_name.xpr"

set sim_log "$project_dir/build/$project_name.sim/sim_1/behav/xsim/simulate.log"


# =====================================================
# STEP 2: Open Vivado project
# =====================================================

if {![file isfile $project_file]} {
    puts "RESULT status=ERROR passed=-1 failed=-1 coverage=NA"
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

# Check whether Vivado reported a simulation error
if {$result != 0} {

    puts "ERROR: $error_message"
    puts "RESULT status=ERROR passed=-1 failed=-1 coverage=NA"

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


# =====================================================
# STEP 7: Read simulation log
# =====================================================

if {[file isfile $sim_log]} {

    set file [open $sim_log r]

    set log_text [read $file]

    close $file


    # Extract simulation results
    regexp {TESTS_PASSED:\s*([0-9]+)} $log_text -> passed

    regexp {TESTS_FAILED:\s*([0-9]+)} $log_text -> failed

    regexp {COVERAGE:\s*([0-9]+)%} $log_text -> coverage


    # Check whether all results were found
    if {$passed >= 0 && $failed >= 0 && $coverage ne "NA"} {

        set status "FAIL"

        # Check whether all acceptance conditions passed
        if {$passed > 0 && $failed == 0 && $coverage == 100 &&
            [string first "ALL TESTS PASSED" $log_text] != -1} {

            set status "PASS"
        }
    }
}


# =====================================================
# STEP 8: Return results to Python AI agent
# =====================================================

puts "RESULT status=$status passed=$passed failed=$failed coverage=$coverage"

puts "SIM_LOG: $sim_log"

close_project
exit 0
