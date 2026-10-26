import json
import vivado_tools

# Step 1: Run build_project.tcl using Vivado batch mode.
print("Running Vivado project script...")

result = vivado_tools.create_project()

print("Vivado exit code:", result["exit_code"])
print("Vivado log file:", result["log_file"])


# Step 2: Summarize the generated Vivado log.
print("\nAnalyzing Vivado log...")

summary = vivado_tools.summarize_vivado_log(
    log_file=result["log_file"],
    filter="default",
    max_messages=0
)


# Step 3: Display the warning summary.
print("\nVivado Log Summary:")

print(json.dumps(summary, indent=4))