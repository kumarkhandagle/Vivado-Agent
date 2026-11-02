puts "Creating Project"

set project_name "fpga_demo"
set device_part "xc7z010clg400-1"

set build_script "C:/Agents/Day5/scripts/build_project.tcl" 

set build_dir [file dirname $build_script]
set project_dir [file dirname $build_dir]

set rtl_dir [file join $project_dir rtl]
set tb_dir [file join $project_dir tb]
set xdc_dir [file join $project_dir xdc]
set build_dir [file join $project_dir build]
set log_dir [file join $project_dir logs]

set project_file [file join $build_dir "${project_name}.xpr"]

if {[file isfile $project_file]} {
    puts "Opening existing project: $project_file"
    open_project $project_file
} else {
    puts "Creating new project: $project_file"
    create_project $project_name $build_dir -part $device_part
}


 add_files -fileset sources_1 [glob -directory $rtl_dir *.v]
 update_compile_order -fileset sources_1
 
 
 add_files -fileset sim_1 [glob -directory $tb_dir *.v]
 update_compile_order -fileset sim_1
 
 add_files -fileset constrs_1 [glob -directory $xdc_dir *.xdc]

 
puts "All files added successfully."
close_project

exit 0