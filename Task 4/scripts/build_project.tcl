
puts "Creating Project"

# =====================================================
# STEP 1: Read configuration passed by Python
# =====================================================

set project_dir  [lindex $argv 0]
set project_name [lindex $argv 1]

set device_part "xc7z010clg400-1"


# =====================================================
# STEP 2: Define project directories
# =====================================================

set rtl_dir   [file join $project_dir rtl]
set tb_dir    [file join $project_dir tb]
set xdc_dir   [file join $project_dir xdc]
set build_dir [file join $project_dir build]

set project_file [file join $build_dir "${project_name}.xpr"]


# =====================================================
# STEP 3: Open or create Vivado project
# =====================================================

if {[file isfile $project_file]} {

    puts "Opening existing project: $project_file"

    open_project $project_file

} else {

    puts "Creating new project: $project_file"

    create_project $project_name $build_dir -part $device_part

}


# =====================================================
# STEP 4: Add RTL files
# =====================================================

set rtl_files [glob -nocomplain -directory $rtl_dir *.v]

if {[llength $rtl_files] > 0} {
    add_files -norecurse -fileset sources_1 $rtl_files
}

update_compile_order -fileset sources_1


# =====================================================
# STEP 5: Add testbench files
# =====================================================

set tb_files [glob -nocomplain -directory $tb_dir *.v]

if {[llength $tb_files] > 0} {
    add_files -norecurse -fileset sim_1 $tb_files
}

update_compile_order -fileset sim_1


# =====================================================
# STEP 6: Add constraint files
# =====================================================

set xdc_files [glob -nocomplain -directory $xdc_dir *.xdc]

if {[llength $xdc_files] > 0} {
    add_files -norecurse -fileset constrs_1 $xdc_files
}


# =====================================================
# STEP 7: Close project
# =====================================================

puts "All files processed successfully."

close_project

exit 0
