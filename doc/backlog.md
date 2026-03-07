# Backlog
- [ ] **Dropdown menu with common CC commands**
  Add a dropdown menu with the taskmill-task, for ease of picking. Writing them by hand is prone to typos. But this should then be separate the dropdown menu from the text input field. We should then have the dropdown menu in a cell to the left of the text cell. This implies moving the text column to B, to make room for the dropdown menu on A. We can then use the remaining of A to have one of the other columns. Perhaps Let it just log the different taskmill commands? Of course: it should NOT be limited to just taskmill commands.

- [ ] **Add multithreading**
  Right now there is one thread in the script that polls all sheets. But it means that the whole process stops when it is waiting for a prompt. This kind of eliminates the idea of having multiple sheets. The idea is then to let the main orchestration thread spawn a dedicated thread per Sheet, which polls its own sheet, and handles every interaction with Claude CLI itself. If the sheet is deleted, the thread dies. If the sheet is renamed (which is handled atm), the thread dies, but the main thread spawns a new thread.

