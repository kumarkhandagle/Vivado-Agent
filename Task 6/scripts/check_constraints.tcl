
# =====================================================
# STEP 1: Read project configuration from Python
# =====================================================

if {[llength $argv] < 2} {
    puts "RESULT stage=constraints status=FAILED reason=MISSING_ARGUMENTS"
    exit 1
}

set project_dir  [lindex $argv 0]
set project_name [lindex $argv 1]

set project_file "$project_dir/build/$project_name.xpr"


# =====================================================
# STEP 2: Open existing Vivado project
# =====================================================

if {![file isfile $project_file]} {
    puts "RESULT stage=constraints status=FAILED reason=PROJECT_NOT_FOUND"
    exit 1
}

if {[catch {open_project $project_file} detail]} {
    puts "RESULT stage=constraints status=FAILED reason=OPEN_PROJECT_ERROR"
    puts "DETAIL: $detail"
    exit 1
}


# =====================================================
# STEP 3: Elaborate RTL design
# =====================================================

set result [catch {

    # Enable loading of XDC constraints.
    set_property elab_load_timing_constraints true [current_fileset]

    # Elaborate RTL.
    synth_design -rtl -rtl_skip_mlo -name rtl_1

} detail]

if {$result != 0} {
    puts "RESULT stage=constraints status=FAILED reason=ELABORATION_ERROR"
    puts "DETAIL: $detail"
    close_project
    exit 1
}


# =====================================================
# STEP 4: Check port constraints
# =====================================================

set missing_pins 0
set missing_standards 0

set ports [get_ports *]

foreach port $ports {

    set pin [get_property PACKAGE_PIN $port]
    set standard [get_property IOSTANDARD $port]

    # Check PACKAGE_PIN.
    if {$pin eq ""} {
        puts "MISSING PACKAGE_PIN: $port"
        incr missing_pins
    }

    # Check IOSTANDARD.
    if {$standard eq "" || $standard eq "DEFAULT"} {
        puts "MISSING IOSTANDARD: $port"
        incr missing_standards
    }
}


# =====================================================
# STEP 5: Determine constraint verification status
# =====================================================

set total_ports [llength $ports]

if {$total_ports == 0 ||
    $missing_pins > 0 ||
    $missing_standards > 0} {

    set status "FAILED"

} else {
    set status "SUCCESS"
}


# =====================================================
# STEP 6: Return results to Python AI agent
# =====================================================

puts "RESULT stage=constraints status=$status total_ports=$total_ports missing_pins=$missing_pins missing_standards=$missing_standards"


# =====================================================
# STEP 7: Close project
# =====================================================

close_project

if {$status eq "FAILED"} {
    exit 1
}

exit 0
