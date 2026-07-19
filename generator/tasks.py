TASKS = [
    "Safety Check",
    "Load State",
    "Select Verse",
    "Generate SEO",
    "Create Video",
    "Upload to YouTube",
    "Update Analytics"
]


def run_tasks():
    print("Today's Tasks")

    for index, task in enumerate(TASKS, start=1):
        print(f"{index}. {task}")
