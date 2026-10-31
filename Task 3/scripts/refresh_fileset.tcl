
# ==========================================================
# STEP 1: Define project directories
# ==========================================================

set project_name "fpga_demo"
set project_dir  "C:/Agents/Day7"

set project_file "$project_dir/build/$project_name.xpr"
set rtl_dir      "$project_dir/rtl"
set tb_dir       "$project_dir/tb"
set xdc_dir      "$project_dir/xdc"


# ==========================================================
# STEP 2: Open the Vivado project
# ==========================================================

set opened_projects [get_projects -quiet]

if {[llength $opened_projects] == 0} {

    if {![file isfile $project_file]} {
        error "Project not found: $project_file"
    }

    open_project $project_file
}


# ==========================================================
# STEP 3: Create procedure to refresh a fileset
# ==========================================================

proc refresh_fileset {fileset folder patterns} {

    # Check whether the directory exists
    if {![file isdirectory $folder]} {
        error "Directory not found: $folder"
    }

    set folder [file normalize $folder]

    # Initialize variables
    set registered_files {}
    set added 0
    set removed 0


    # ------------------------------------------------------
    # STEP 3A: Get files currently registered in Vivado
    # ------------------------------------------------------

    set fileset_object [get_filesets $fileset]

    set vivado_files [get_files -quiet -of_objects $fileset_object]


    # ------------------------------------------------------
    # STEP 3B: Remove references to deleted files
    # ------------------------------------------------------

    foreach file_object $vivado_files {
	
        # Get full path of the registered file
        set file_path [get_property NAME $file_object]
        set file_path [file normalize $file_path]

        # Check whether the file exists on disk
        set file_exists [file exists $file_path]

        # Get directory containing the file
        set file_dir [file dirname $file_path]



        if {$file_dir eq $folder && !$file_exists} {

            remove_files -fileset $fileset $file_object

            incr removed

            puts "REMOVED ($fileset): $file_path"

        } else {

            # Remember files that remain registered
            lappend registered_files $file_path
        }
    }


    # ------------------------------------------------------
    # STEP 3C: Find physical files and add missing ones
    # ------------------------------------------------------

    foreach pattern $patterns {

        # Find files matching the current extension
        set disk_files [glob -nocomplain -types f \
            -directory $folder $pattern]

        foreach file_path $disk_files {

            set file_path [file normalize $file_path]

            # Search for the file in the registered list
            set index [lsearch -exact $registered_files $file_path]

            # -1 means the file is not registered
            if {$index == -1} {

                add_files -norecurse -fileset $fileset $file_path

                lappend registered_files $file_path

                incr added

                puts "ADDED ($fileset): $file_path"
            }
        }
    }


    # ------------------------------------------------------
    # STEP 3D: Return number of added and removed files
    # ------------------------------------------------------

    return [list $added $removed]
}


# ==========================================================
# STEP 4: Refresh RTL files
# ==========================================================

set rtl_result [refresh_fileset sources_1 $rtl_dir {*.v *.sv}]

lassign $rtl_result rtl_added rtl_removed


# ==========================================================
# STEP 5: Refresh testbench files
# ==========================================================

set tb_result [refresh_fileset sim_1 $tb_dir {*.v *.sv}]

lassign $tb_result tb_added tb_removed


# ==========================================================
# STEP 6: Refresh constraint files
# ==========================================================

set xdc_result [refresh_fileset constrs_1 $xdc_dir {*.xdc}]

lassign $xdc_result xdc_added xdc_removed


# ==========================================================
# STEP 7: Update compile order
# ==========================================================

update_compile_order -fileset sources_1
update_compile_order -fileset sim_1


# ==========================================================
# STEP 8: Return summary to the Python AI agent
# ==========================================================

puts "RESULT status=OK rtl_added=$rtl_added rtl_removed=$rtl_removed tb_added=$tb_added tb_removed=$tb_removed xdc_added=$xdc_added xdc_removed=$xdc_removed"
