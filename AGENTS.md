**Don't work in `main` without permission**
Before writing ANY files within the working directory, check to see if the current branch is `main`. If so, ALWAYS check with the user before proceeding. Ask the user if they would like to write changes in `main`, or switch to a new branch before writing. If the user chooses to switch to a new branch, suggest a branch name but allow the user to customize it. If the working directory is not under version control, allow writes.

**Rules for conducting a "Grill Me" session**
  * At the end of a `/grill-me` session, prior to implementation, check out a new branch. Name it something meaningful, based on the work that was discussed. Keep it short (four words or less, separated by dashes)

**Rules for feature dev**
  * After completing an implementation plan:
    1. ALWAYS commit the code using git, with a _conventional commit_ message