**Don't work in `main` without permission**
Before writing ANY files within the working directory, check to see if the current branch is `main`. If so, ALWAYS check with the user before proceeding. Ask the user if they would like to write changes in `main`, or switch to a new branch before writing. If the user chooses to switch to a new branch, suggest a branch name but allow the user to customize it. If the working directory is not under version control, allow writes.

**Rules for conducting a "Grill Me" session**
  * At the end of a `/grill-me` session, prior to implementation, check out a new branch. Name it something meaningful, based on the work that was discussed. Keep it short (four words or less, separated by dashes)

**Rules for feature dev**
  * After completing an implementation plan:
    1. ALWAYS commit the code using git, with a _conventional commit_ message
    2. Prompt the user for the next step and proceed according to the user's choice:
      a. push the current branch to remote and open a pull request, with a description explaning the change
      b. push the current branch to remote but DO NOT open a pull request
      c. merge the current branch to main and checkout main
      d. do nothing
