
# =====================================================
# STEP 1: Read project configuration from Python
# =====================================================

if {[llength $argv] < 2} {
    puts "RESULT stage=device_part status=FAILED reason=MISSING_ARGUMENTS"
    exit 1
}

set project_dir  [lindex $argv 0]
set project_name [lindex $argv 1]

set project_file "$project_dir/build/$project_name.xpr"

# Expected FPGA device.
set expected_part "xc7z010clg400-1"


# =====================================================
# STEP 2: Open existing Vivado project
# =====================================================

if {![file isfile $project_file]} {
    puts "RESULT stage=device_part status=FAILED reason=PROJECT_NOT_FOUND"
    exit 1
}

if {[catch {open_project $project_file} error_message]} {
    puts "RESULT stage=device_part status=FAILED reason=OPEN_PROJECT_ERROR"
    puts "DETAIL: $error_message"
    exit 1
}


# =====================================================
# STEP 3: Check current FPGA device
# =====================================================

set current_part [get_property PART [current_project]]
set action "UNCHANGED"

if {$current_part ne $expected_part} {

    # Check whether the expected device is available.
    if {[llength [get_parts -quiet $expected_part]] == 0} {
        puts "RESULT stage=device_part status=FAILED reason=PART_NOT_FOUND"
        close_project
        exit 1
    }

    # Remove existing board assignment, if any.
    set board_part [get_property BOARD_PART [current_project]]

    if {$board_part ne ""} {
        reset_property BOARD_PART [current_project]
    }

    # Update FPGA device.
    if {[catch {
        set_property PART $expected_part [current_project]
    } error_message]} {
        puts "RESULT stage=device_part status=FAILED reason=UPDATE_ERROR"
        puts "DETAIL: $error_message"
        close_project
        exit 1
    }

    set action "UPDATED"
}


# =====================================================
# STEP 4: Verify final FPGA device
# =====================================================

set final_part [get_property PART [current_project]]

if {$final_part eq $expected_part} {
    set status "SUCCESS"
} else {
    set status "FAILED"
}


# =====================================================
# STEP 5: Return result to Python AI agent
# =====================================================

puts "RESULT stage=device_part status=$status action=$action part=$final_part"


# =====================================================
# STEP 6: Close project
# =====================================================

close_project

if {$status eq "FAILED"} {
    exit 1
}

exit 0
