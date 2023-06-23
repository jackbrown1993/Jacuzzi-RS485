""" cursesui.py provides you with a simple text-mode windowing user
interface that encapsulates the curses.py library while supporting
both asychronous processes and standard logging.
"""

# Interface to the operating system.
import sys
import logging

# Make our logging instance visible throughout this module.
log = logging.getLogger(__name__)

import traceback
import time

# Interface to the Python curses library.
import curses
import curses.ascii

# Support for running asynchronous programs concurrently.
import asyncio

# Support for enumerated constants in Python.
from enum import Enum


class Align(Enum):
    """Alignment enum types for Textfields"""

    NOTSET = 0
    LEFT = 1
    CENTER = 2
    RIGHT = 3


class Textfield:
    """Encapsulates a string of text at an absolute row and column
    position in a Window object, with optional alignment. Supports
    multiline strings where the lines are separated by a newline
    character.

    Textfields default to read-only.  You can make them editable
    by adding an EditDialog instance to them.
    """

    def __init__(self, row, col, align: Align = Align.NOTSET):
        self.win = None
        self.row = row if row >= 0 else 0
        self.col = col if col >= 0 else 0
        self.lines = []
        self.update_cb = None
        self.visible = False
        self.align = align
        self.set_selectable(False)
        self.unselect()
        self.dialog = None

        # Attributes to apply to this Textfield. Bitwise-OR these
        # to combine multiple attributes.
        self.attrs = curses.A_NORMAL

    def set_alignment(self, align: Align):
        """Configure the alignment type for this Textfield"""
        self.align = align

    def add_to(self, win):
        """Adds this Textfield to the given Window instance"""
        self.win = win

    def write(self, txt):
        """Removes any prior string from its parent Window by
        hiding it, then adds this new text string to its Window
        object. Supports multline strings.
        """
        self.hide()

        # Strip any trailing newline chars to remove
        # any pointless trailing empty lines.
        self.lines = txt.rstrip("\n").split("\n")
        self.show()

    def get_text(self):
        """Returns the (possibly multiline) text string
        in this Textfield as a single string. Multiple lines
        will be separated by a newline character.
        """
        return "\n".join(self.lines)

    def get_required_rows(self):
        """Returns the number of rows required to display
        all lines in this Textfield.
        """
        return len(self.lines)

    def get_required_cols(self):
        """Returns the minumum number of columns required
        to display all lines in this Textfield
        """
        return len(max(self.lines, key=len))

    def _get_col_offset(self, text):
        """Implements right, left and center alignment"""
        if self.align == Align.RIGHT:
            return -len(text)
        elif self.align == Align.CENTER:
            return -int(len(text) / 2)
        else:
            return 0

    def show(self):
        """Makes this Textfield visible by adding it to the
        window at the TextField's row and column position.
        Supports multiline text strings where the lines are
        separated by a newline character.
        """
        self.visible = True

        # Call addnstr() only when it makes sense to do so
        if self.win is not None and self.win.cwin is not None and len(self.lines) != 0:
            # Get the row constraint for this Textfield
            maxlines = self.win.get_last_row() - self.row + 1

            for i in range(min(len(self.lines), maxlines)):
                # Get the actual start row, column and max
                # length for this line.
                start_row = self.row + i
                start_col = self.col + self._get_col_offset(self.lines[i])
                maxchars = self.win.get_last_col() - start_col + 1

                # Quit if nothing to add
                if maxchars <= 0:
                    continue
                try:
                    # Turn on the attributes for this write
                    self.win.cwin.attron(self.attrs)

                    # Write the text string into the curses window object
                    self.win.cwin.addnstr(start_row, start_col, self.lines[i], maxchars)

                    # Done writing so turn off the attributes
                    self.win.cwin.attroff(self.attrs)

                except Exception as e:
                    # Done writing so turn off the attributes
                    self.win.cwin.attroff(self.attrs)
                    if log is None:
                        # test comment
                        print("Log is None in show()")
                    else:
                        log.warning(
                            (
                                'In show(): At ({0},{1}) "{2}" '
                                "is outside of its window"
                            ).format(start_row, start_col, self.lines[i])
                        )
                    break

    def hide(self):
        """Makes this TextField invisible by overwriting the
        text with a line of spaces the same length, at the same
        row and column position. Supports multiline text strings
        where the lines are separated by newline characters.
        """
        self.visible = False

        # Call addnstr() only when it makes sense to do so
        if self.win is not None and self.win.cwin is not None and len(self.lines) != 0:
            # Get the row constraint for this Textfield
            maxlines = self.win.get_last_row() - self.row + 1

            for i in range(min(len(self.lines), maxlines)):
                # Get a string of spaces as long as the text line
                blanktxt = f'{"":<{len(self.lines[i])}}'

                # Get the actual start row, column and max
                # length for this line.
                start_row = self.row + i
                start_col = self.col + self._get_col_offset(self.lines[i])
                maxchars = self.win.get_last_col() - start_col + 1

                # Quit if nothing to add
                if maxchars <= 0:
                    continue
                try:
                    # Turn off the Textfield's attributes as we
                    # write blank characters.
                    self.win.cwin.attroff(self.attrs)
                    self.win.cwin.addnstr(start_row, start_col, blanktxt, maxchars)
                except Exception as e:
                    if log is None:
                        # test comment
                        print("Log is None in hide()")
                    else:
                        log.warning(
                            (
                                'In hide(): At ({0},{1}) "{2}" '
                                "is outside of its window"
                            ).format(start_row, start_col, self.lines[i])
                        )
                    break

    def move(self, row, col, constrain=True):
        """Moves this Textfield to a new row and column position.
        The values are normally clamped to remain inside the
        parent window, unless constrain is False.

        An unconstrained move is only useful when the new location
        is on a Window's border.  Any other unconstrained location
        will generate a warning that the Textfield is outside of its
        Window.
        """
        was_visible = self.visible
        if was_visible:
            self.hide()
        if constrain:
            self.row = self.win.constrain_row(row)
            self.col = self.win.constrain_col(col)
        else:
            self.row = row
            self.col = col
        if was_visible:
            self.show()

    def set_update_cb(self, update_cb):
        """Provide a callback routine to update this
        Textfield's content. The callback takes no
        parameters and returns a fully formatted text
        string for display.
        """
        self.update_cb = update_cb

    def update(self):
        """Update this Textfield by calling its
        update callback function, if one has been
        provided.
        """
        if self.update_cb is not None:
            self.write(self.update_cb())

    def add_attrs(self, attrs):
        """Add these character attributes for this
        Textfield. You can specify multiple attributes
        by combining the curses character attribute constants
        with a bitwise-OR.
        """
        self.attrs |= attrs

    def remove_attrs(self, attrs):
        """Removes these character attributes from
        this Textfield. You can specify multiple
        attributes by combining the curses character
        attribute constants with a bitwise-OR.
        """
        self.attrs &= ~attrs

    def get_attrs(self):
        """Returns the current default character
        attributes for this Textfield.
        """
        return self.attrs

    def set_selectable(self, flag: bool = True):
        """Allow or prevent selecting this Textfield."""
        self.selectable = flag

    def select(self):
        """Select this Textfield, if selectable."""
        if self.selectable:
            self.selected = True

    def unselect(self):
        """Unselect this Textfield."""
        self.selected = False

    def draw_selection(self, showit: bool = True):
        """Changes the attributes of this Textfield
        to indicate whether or not it is selected.
        You can override this if you want to
        change how a selected Textfield is displayed.

        Note: this is called during every repaint.
        """
        attr = curses.A_UNDERLINE
        if self.selected and showit:
            self.add_attrs(attr)
        else:
            self.remove_attrs(attr)

    def set_dialog(self, dialog: "EditDialog"):
        """Installs an EditDialog instance
        for this Textfield.  The dialog allows
        the user to modify the data shown by
        the Textfield.
        """
        self.dialog = dialog
        if dialog is not None:
            self.set_selectable(True)
        else:
            set_selectable(False)

    def get_dialog(self):
        """Returns the currently installed
        EditDialog instance, or None if one
        is not installed.
        """
        return self.dialog


class KeyResponse:
    """This class encapsulates a Window's responses to a
    specific key or group of keys. It is used by the CursesUI
    class to bind one or more key values to a response routine.

    The name parameter is required; it should be a unique
    text string that you can use later to retrieve that specific
    instance.

    While not recommended, you can actually create and install
    more than one KeyResponse instance with the same name string.
    However the system will match and then react only to the first
    one it finds -- which may cause subtle, unexpected behavior.

    After creating a KeyResponse instance, you can bind or
    unbind response routines to it at any time.

    When a user keyhit passed to the KeyResponse _respond()
    method matches one of its keyvalues, the instance will call
    the current response routine bound to it.

    Each response routine receives the matched keyvalue, which
    allows you to have a single response routine that can respond
    to several similar or related key values, including the entire
    group.  Thus a single KeyResponse instance can respond to a
    single key (e.g. TAB) or a whole group -- for example a list
    of keyvalues or a filtered group e.g. "any digit" by installing
    a filter function such as curses.ascii.isdigit().

    Each KeyResponse instance only calls one response routine
    for any one keyhit passed to _respond(). But if you bind
    another response routine to it, that new binding will
    non-destructively "override" the previous binding.  The
    unbind() method by default will unbind only the most recent
    binding, thereby restoring the previous binding (if any).
    """

    def __init__(self, name, keyvalue=None):
        self.name = name
        self.keyvalues = []
        if keyvalue is not None:
            self.add_keyvalues(keyvalue)
        self.responses = []
        self.filter = lambda keyhit: False

    def get_name(self):
        """Returns the name string that identifies
        this KeyResponse instance.
        """
        return self.name

    def add_keyvalues(self, values):
        """Adds one or more integer keyvalues that this
        KeyResponse instance will respond to. The given
        values can be either a single integer or a list
        of integers.
        """
        try:
            for value in values:
                self.keyvalues.append(value)
        except:
            self.keyvalues.append(values)

    def remove_keyvalues(self, values: list):
        """Removes one or more integer keyvalues that this
        KeyResponse instance responds to. Ignores any
        integer values that are not found in the list.
        """
        for value in values:
            try:
                self.keyvalues.remove(value)
            except:
                continue

    def get_keyvalues(self):
        """Returns the array of specific
        integer key values that this KeyResponse
        instance will recognize.  This does
        not include values matched through
        any filter routine (e.g. isdigit()
        added to this KeyResponse instance.
        """
        return self.keyvalues

    def set_filter(self, filter):
        """Installs a filter routine (e.g.
        isdigit() to specify key values this
        KeyResponse instance will respond to.
        """
        self.filter = filter

    def bind(self, response_routine):
        """Add this response routine to the
        the list of responses to this keyhit.
        """
        self.responses.append(response_routine)

    def unbind(self, response_routine=None):
        """Removes this response routine from the
        list of key responses, or the one most
        recently added if None.
        """
        # prevent popping an empty list (e.g. dialog Windows)
        if not self.responses:
            return
        if response_routine is not None:
            self.responses.remove(response_routine)
        else:
            self.responses.pop()

    def _respond(self, keyhit):
        # Calls the most recently bound response routine when
        # the keyhit is found in the list of keyvalues, or an
        # installed filter routine returns True when given the
        # keyhit.
        #
        # Each response routine gets the Window instance with the
        # matching KeyResponse instance as well as the key value
        # that matched.
        #
        # Returns True on a match, False otherwise.

        if self.responses and (keyhit in self.keyvalues or self.filter(keyhit)):
            self.responses[-1](keyhit)
            return True
        return False


class Window:
    """Base class for common Window object behaviors."""

    def __init__(self, parent, nrows, ncols, title=None):
        # Current dimensions. These may be smaller than
        # max dimensions when the Window is constrained
        # by its parent.
        self.nrows = nrows
        self.ncols = ncols

        # Max dimensions when unconstrained by a
        # parent.
        self.maxrows = nrows
        self.maxcols = ncols

        # The curses window object associated with this
        # Window object.
        self.cwin = None

        # The Window instance containing this one
        self.parent = parent

        # The list of child Window instances contained
        # within this one.
        self.children = []

        # The list of Textfield instances contained
        # within this Window.
        self.textfields = []

        # The list of KeyResponse instances handled
        # by this Window.
        self.keys = []

        # Default Window characteristics
        self.has_border = True
        self.border_height = 1  # In rows per horizontal border line
        self.border_width = 1  # In columns per vertical border line
        self.set_selectable()  # Windows are selectable by default
        self.unselect()  # Windows are unselected by default

        # Character attributes to apply to the entire window.
        # Bitwise-OR these to combine multiple attributes.
        self.attrs = curses.A_NORMAL

        # Automatically add this new Window to its parent, if
        # there is one.
        if parent is not None:
            parent.add_child(self)

        # Automatically create and add a Textfield for the title,
        # if a title is provided.
        if title is not None:
            self.add_title(title)

        # Counter for multiple resize() calls needed to
        # overcome a curses wierdness.
        self._resize_count = 0

    def add_title(self, newtitle):
        """Adds a title Textfield to this Window"""
        if newtitle is None:
            self.remove_title()
        else:
            self.titlefield = Textfield(
                self.get_first_row() - 1, self.get_center_col(), Align.CENTER
            )
            self.add_field(self.titlefield)
            self.titlefield.write(newtitle)

    def _reposition_title(self):
        """Repositions the title Textfield for this Window. Used
        to adjust a Window's title position after the Window has
        been resized with persistent = True.
        """
        # Reposition the title Textfield. Don't constrain
        # the move though, since we intentially want it to
        # be on the border of the Window.
        self.titlefield.move(self.get_first_row() - 1, self.get_center_col(), False)

    def remove_title(self):
        """Removes the title Textfield from this Window"""
        self.remove_field(self.titlefield)
        self.titlefield = None
        self.title = None

    def get_title(self):
        """Returns the Window's title string, or None
        if there isn't one.
        """
        if self.titlefield is not None:
            return self.titlefield.get_text()
        return None

    def add_child(self, win):
        """Adds a child window to this one. Child windows get
        repainted whenever this window is repainted, in the
        order they were added. So for children that may overlap,
        add the windows in order from bottom to topmost.
        """
        self.children.append(win)

    def remove_child(self, win):
        """Removes a child window from this one."""
        self.children.remove(win)

    def get_children(self) -> list:
        """Returns the list of this Window's children.
        Probably not necessary but provided here so
        that it may be overridden.
        """
        return self.children

    def get_first_child(self):
        """Returns the bottommost child of this Window
        or None if there are no child Windows.
        """
        if len(self.get_children()) == 0:
            return None
        else:
            return self.get_children()[0]

    def get_next_child(self, child: "Window"):
        """Returns the next child up, in this Window. If
        the given child is not found, returns None.  If the
        given child is the topmost child, then this will
        return the bottommost child Window.
        """
        leni = len(self.get_children())
        for i in range(leni):
            if self.get_children()[i] == child:
                nxti = (i + 1) % leni
                return self.get_children()[nxti]
        return None

    def get_child_by_title(self, title):
        """Returns the first child in this
        Window with the given title, or None
        if not found.
        """
        for child in self.get_children():
            name = child.get_title()
            if name is not None and name == title:
                return child
        return None

    def set_selectable(self, flag: bool = True):
        """Allow or prevent selecting this Window."""
        self.selectable = flag

    def select(self):
        """Select this Window, if selectable."""
        if self.selectable:
            self.selected = True

    def unselect(self):
        """Unselect this Window."""
        self.selected = False

    def select_child(self, given):
        """Selects the given child Window after unselecting
        any currently selected Window. Returns the newly
        selected child Window, or None on failure.
        """
        if given != None and given.selectable:
            child = self.get_selected_child()
            if child != None:
                child.unselect()
            given.select()
            return given
        return None

    def get_selected_child(self):
        """Returns the first selected child Window in
        this Window. If no child Window is currently
        selected then this method will select the first
        child Window and return that.  If there are no
        child Windows then this method returns None.
        """
        # Find and return the first selected child
        for child in self.get_children():
            if child.selected:
                return child

        # No child is currently selected so select
        # and return the first child.
        child = self.get_first_child()
        if child is not None:
            child.select()
            return child

        # There are no child Windows at all
        return None

    def select_child_by_title(self, title):
        """Selects a child of this Window with the given title.
        Returns the child Window, or None if not found or not
        selectable.
        """
        child = self.get_child_by_title(title)
        if child != None and child.selectable:
            self.unselect_all_children()
            child.select()
            return child
        return None

    def unselect_all_children(self):
        """Insures that no child Windows are selected"""
        for child in self.get_children():
            if child.selected:
                child.unselect()

    def add_field(self, txtfield: Textfield):
        """Adds a Textfield to this Window object."""
        txtfield.add_to(self)
        self.textfields.append(txtfield)

    def remove_field(self, txtfield: Textfield):
        """Removes a Textfield from this Window object."""
        txtfield.add_to(None)
        self.textfields.remove(txtfield)

    def get_textfields(self) -> list:
        """Returns the list of this Window's Textfields.
        Probably not necessary but provided here so
        that it may be overridden.
        """
        return self.textfields

    def get_first_field(self):
        """Returns the first Textfield in this Window
        or None if there are no Textfields.

        Note that the Window's title Textfield is a
        special case so we ignore it here.
        """
        leni = len(self.get_textfields())
        for i in range(leni):
            tf = self.get_textfields()[i]
            if tf != self.titlefield:
                return tf
        return None

    def get_next_field(self, given: Textfield):
        """Returns the next Textfield in this Window.
        If the given Textfield is not found, returns None.
        If the given Textfield is the last in this Window,
        this method will return the first Textfield.

        Note that the Window's title Textfield is a
        special case so we ignore it here.
        """
        # Quit if the given field is not found
        try:
            gi = self.get_textfields().index(given)
        except:
            return None

        # Find the next field, starting from given
        n = len(self.get_textfields())
        for i in range(n):
            # Use modulo to wrap from last to first
            nxti = (gi + i + 1) % n
            # Get a copy of the next field
            nxtf = self.get_textfields()[nxti]
            # Done unless next is the title
            if nxtf != self.titlefield:
                break
        return nxtf

    def select_field(self, given):
        """Selects the given Textfield after unselecting
        any currently selected Textfield and makes the
        selection visible. Returns the newly selected
        Textfield, or None on failure.
        """
        if given != None and given.selectable:
            sf = self.get_selected_field()
            if sf != None:
                sf.unselect()
            given.select()
            self.show_selected_field(True)
            return given
        return None

    def get_selected_field(self):
        """Returns the first selected Textfield in
        this Window. If no Textfield is currently
        selected then this method will select the first
        Textfield and return that.  If there are no
        Textfields then this method returns None.

        Note that the Window's title Textfield is a
        special case so we ignore it here, although
        it should never be selectable anyway.
        """
        # Find and return the first selected Textfield
        tflist = self.get_textfields()
        for tf in tflist:
            if tf.selected and tf != self.titlefield:
                return tf

        # No Textfield is currently selected so find the
        # first selectable one and select it if found.
        for tf in tflist:
            if tf.selectable and tf != self.titlefield:
                tf.select()
                return tf

        # No selectable Textfields at all
        return None

    def show_selected_field(self, flag: bool = True):
        """Highlights the currently selected
        Textfield in this Window.

        Note that the Window's title Textfield is a
        special case so we ignore it here, although
        it should never be selectable anyway.
        """
        for tf in self.get_textfields():
            if tf != self.titlefield:
                tf.draw_selection(flag)

    def draw_selection(self):
        """Changes the attributes of the Window
        to indicate whether or not it is selected.
        You can override this if you want to
        change how a selected Window is displayed.

        Note: this is called during every repaint.
        """
        attr = curses.A_BOLD
        if self.selected:
            self.add_attrs(attr)
        else:
            self.remove_attrs(attr)

    def unselect_all_fields(self):
        """Insures that no Textfields in this Window
        are selected.
        """
        for tf in self.get_textfields():
            if tf.selected:
                tf.unselect()

    def show_all_fields(self):
        """Makes all Textfields visible in this Window object."""
        for tf in self.textfields:
            tf.show()

    def update_all_fields(self):
        """Updates all Textfields in this Window object by
        calling each Textfield's update callback function.
        """
        for tf in self.textfields:
            tf.update()

    def get_first_col(self):
        """Returns the leftmost writeable column value
        inside of this Window.
        """
        return self.border_width if self.has_border else 0

    def get_center_col(self):
        """Finds the approximate center column inside of
        this Window.
        """
        # Add 1 to round up (looks better in narrow Windows)
        return int(self.get_last_col() / 2) + 1

    def get_last_col(self):
        """Returns the rightmost writeable column value
        inside of this Window.
        """
        last_col = max(self.ncols - 1, 0)
        bw = self.border_width if self.has_border else 0
        if last_col > bw:
            last_col = last_col - bw
        return last_col

    def constrain_col(self, col):
        """Clamps the column value to be inside this Window"""
        # Note: get_first_col() and get_last_col() account
        # for any border this Window has.
        return min(self.get_last_col(), max(self.get_first_col(), col))

    def get_first_row(self):
        """Returns the topmost writeable row value
        inside of this Window.
        """
        return self.border_height if self.has_border else 0

    def get_center_row(self):
        """Finds the approximate middle row inside
        this Window.
        """
        # Add 1 to round up (looks better?)
        return int(self.get_last_row() / 2) + 1

    def get_last_row(self):
        """Returns the bottommost writeable row value
        inside this Window.
        """
        last_row = max(self.nrows - 1, 0)
        bh = self.border_height if self.has_border else 0
        if last_row > bh:
            last_row = last_row - bh
        return last_row

    def constrain_row(self, row):
        """Clamps the given row value to be inside
        this Window object.
        """
        # Note: get_first_row() and get_last_row() account
        # for any border this Window has.
        return min(self.get_last_row(), max(self.get_first_row(), row))

    def show_border(self):
        """Displays a border around this Window object."""
        self.has_border = True

    def hide_border(self):
        """Removes the border around this Window"""
        self.has_border = False

    def draw_border(self):
        """Draws a single line border around the
        inside perimeter of this Window. You can
        override this if you need more complex
        borders.

        Note: this is called during every repaint.
        """
        if self.has_border:
            # self.cwin.border()
            self.cwin.box()

    def add_attrs(self, attrs):
        """Adds the character attributes for the inside
        of this Window. You can specify multiple
        attributes by combining the curses character
        attribute constants with a bitwise-OR.
        """
        self.attrs |= attrs

    def remove_attrs(self, attrs):
        """Removes these character attributes from
        the inside of this Window. You can specify multiple
        attributes by combining the curses character
        attribute constants with a bitwise-OR.
        """
        self.attrs &= ~attrs

    def resize(self, nrows, ncols, persistent=True):
        """Resizes the curses window object to the new
        dimensions.

        A temporary change only affects the nrows and
        ncols attributes of the Window instance and the
        curses window object, shrinking the window as
        needed to remain inside its parent.

        A persistent change modifies the maxrows and
        maxcols attributes which are the dimensions of
        the Window object when unconstrained by the
        size of its parent.
        """
        # If we're changing the window size and it's
        # persistent then set the max row and column
        # attributes to the new values.  In any case
        # do not resize the window beyond its current
        # max row and column values.
        #
        # On each change, reset the _resize_count
        # attribute to insure that the change is
        # accurately displayed on screen.
        if self.nrows != nrows:
            if persistent:
                self.maxrows = nrows
            self.nrows = min(nrows, self.maxrows)
            self._resize_count = 2
        if self.ncols != ncols:
            if persistent:
                self.maxcols = ncols
            self.ncols = min(ncols, self.maxcols)
            self._resize_count = 2

        # Update the entire curses window object if our Window
        # object has changed size.
        #
        # We should only need to call the curses resize() method
        # once when resizing. But unless it is called a second
        # time the borders may not return to the actual last row
        # or last column position as they should, until the next
        # curses resize() call occurs.
        #
        # This seems to always happen with the bottom row border,
        # and only occasionally happen with the right side border
        # -- which suggests to me that it is somehow a timing
        # related issue in the underlying curses library.
        #
        # In any case we use self._resize_count here to call
        # resize() more than once, each time we need to resize
        # the window. This insures that the curses window object
        # always accurately reflects the state of our Window
        # object.
        if self.cwin is not None and self._resize_count > 0:
            self.cwin.resize(nrows, ncols)
            self._resize_count -= 1

        # If the resize is persistent, then reposition
        # the Window's title. We want to do this after
        # the curses window object has been resized to
        # make sure it will accommodate the new title
        # position.
        if persistent:
            self._reposition_title()

    def _constrain(self):
        """Temporarily constrains the Window to remain within
        the current dimensions of the parent, if needed.

        Returns True if the Window is still visible, else False.
        """
        # Get the current row and column limits
        row_limit = self.parent.get_last_row()
        col_limit = self.parent.get_last_col()

        # This Window is invisible if the upper left corner is
        # outside of the parent's limits.
        if self.ulcrow > row_limit or self.ulccol > col_limit:
            return False

        # Otherwise, limit the lower right corner of the Window's
        # rectangle.
        bh = self.border_height if self.has_border else 0
        bw = self.border_width if self.has_border else 0
        lrcrow = min(self.ulcrow + self.maxrows - bh, row_limit)
        lrccol = min(self.ulccol + self.maxcols - bw, col_limit)
        max_height = lrcrow - self.ulcrow + 1
        max_width = lrccol - self.ulccol + 1

        # Temporarily resize the curses window object if needed
        self.resize(max_height, max_width, False)

        return True

    def refresh(self):
        """Transfers this window's content to the curses virtual
        screen.
        """
        self.cwin.noutrefresh()

    def repaint(self):
        """Constrains this curses window object as needed to fit
        inside its parent,  If still visible then this routine
        clears this curses window object, repaints its contents
        and then does the same for any child windows, in order,
        from bottom child to top. Finally it transfers this
        window's contents to the curses virtual screen.
        """
        # Constrain the Window and if no longer visible then
        # no need to repaint anything.
        if not self._constrain():
            return

        # Set the current background character and attributes
        # for this entire curses window object.
        self.cwin.bkgd(" ", self.attrs)

        # Fill the curses window object with background
        # characters.
        self.cwin.erase()

        # Draw a border around the entire curses window object
        # if it should have one, and highlight the Window if
        # it is currently selected.
        self.draw_border()
        self.draw_selection()

        # Update all of this Window's Textfields and then
        # make sure they are all visible.
        self.update_all_fields()
        self.show_all_fields()

        # Transfer the contents of this curses window object
        # to the virtual screen buffer (but not the physical
        # display screen yet). This must happen before the
        # children get repainted for them to be visible.
        self.refresh()

        # Repaint any child windows in order from bottom to top
        for child in self.children:
            child.repaint()

    def add_key(self, key: KeyResponse):
        """Adds this KeyResponse instance to the
        CursesUI's list of active key bindings.
        """
        self.keys.append(key)

    def remove_key(self, key: KeyResponse):
        """Deletes this KeyResponse instance from the
        CursesUI's list of active key bindings.
        """
        self.keys.remove(key)

    def get_key(self, name) -> KeyResponse:
        """Returns the KeyResponse instance with the
        given name string. If not found then this method
        will return None.
        """
        for key in self.keys:
            if key.name == name:
                return key
        return None

    def _process_keyhit(self, keyhit):
        """Search the list of KeyResponse instances
        until a KeyResponse matches this keyhit.

        When there is a currently selected child
        Window, start the search there first.

        When there is a match, quit searching further
        and call the current key response routine
        bound to the matching KeyResponse. The
        response routine gets passed the Window
        with the matching KeyResponse instance, as
        well as the key value that matched.
        """
        child = self.get_selected_child()
        if child is not None and child._process_keyhit(keyhit):
            return True
        for key in self.keys:
            if key._respond(keyhit):
                return True
        return False

    def kr_select_next_child(self, _):
        """This key response routine finds the currently
        selected child Window. If found it unselects it,
        finds the next selectable child, and selects that
        one.  Returns the newly selected child Window, or
        None on failure.
        """
        sc = self.get_selected_child()
        if sc != None:
            sc.unselect()
            n = len(self.get_children())
            for i in range(n):
                nxtc = self.get_next_child(sc)
                sc = self.select_child(nxtc)
                if sc != None:
                    return sc
                sc = nxtc
        return None

    def kr_select_next_field(self, _):
        """This key response routine finds the
        currently selected Textfield.  If found
        it unselects it, finds the next selectable
        Textfield, and selects that one.  Returns
        the newly selected Textfield, or None on
        failure.
        """
        sf = self.get_selected_field()
        if sf != None:
            sf.unselect()
            n = len(self.get_textfields())
            for i in range(n):
                # Note: get_next_field() ignores
                # titlefields.
                nxtf = self.get_next_field(sf)
                sf = self.select_field(nxtf)
                if sf != None:
                    return sf
                sf = nxtf
        return None

    def kr_begin_child_edit(self, _):
        """This key response routine begins an edit
        session on the currently selected child Window.

        In that child Window, it highlights the currently
        selected Textfield and allows the user to move the
        selection to other selectable Textfields.

        It also installs the key responses that navigate
        within the Window and end the child Window edit
        session.
        """
        # Find the currently selected child Window.
        # Quit if none are selected or selectable.
        child = self.get_selected_child()
        if child == None:
            return

        # If no Textfields are currently selected,
        # this will select the first one. Quit if
        # there are no selectable Textfields.
        field = child.get_selected_field()
        if field == None:
            return

        # Make the currently selected Textfield
        # visible.
        child.show_selected_field(True)

        # The ENTER key now should begin editing
        # the currently selected Textfield.
        self.get_key("enter").bind(field.dialog.kr_begin_field_edit)

        # The TAB key now should select Textfields
        # instead of child Windows.
        self.get_key("tab").bind(child.kr_select_next_field)

        # Create and install a KeyResponse instance for ESCAPE.
        esc_key = KeyResponse("esc", curses.ascii.ESC)
        self.add_key(esc_key)

        # The ESC key should end editing the child Window.
        esc_key.bind(self.kr_end_child_edit)

    def kr_end_child_edit(self, _):
        """This key response routine finds the currently
        selected child Window, and unhighlights the
        currently selected Textfield. Lastly it restores
        the previous key bindings.
        """
        child = self.get_selected_child()
        child.show_selected_field(False)

        # Restore the previous key bindings
        self.get_key("enter").unbind()
        self.get_key("tab").unbind()
        self.get_key("esc").unbind()


class SubWindow(Window):
    """Encapsulates the behavior of a curses subwindow. Subwindows
    share the same buffer space as their parent window, so writing to the
    subwindow will overwrite anything under it in the parent. Refreshing
    a subwindow only refreshes that area in the parent window object.
    """

    def __init__(self, parent, nrows, ncols, ulcrow, ulccol, title=None):
        super().__init__(parent, nrows, ncols, title)
        self.ulcrow = ulcrow
        self.ulccol = ulccol
        self.parent = parent

        # Make sure the curses window is constrained to fit inside
        # its parent when it is created. Otherwise the call to
        # subwin() might generate a "curses function returned NULL"
        # fatal error.
        self._constrain()
        self.cwin = parent.cwin.subwin(self.nrows, self.ncols, self.ulcrow, self.ulccol)

    # Probably not needed but here for completeness anyway.
    def __del__(self):
        if self.cwin is not None:
            del self.cwin

    def move(self, row, col):
        """Moves this SubWindow to a new row and column position.
        The values are clamped to remain inside the parent window.
        """
        self.ulcrow = self.parent.constrain_row(row)
        self.ulccol = self.parent.constrain_col(col)

        # Update the curses subwindow with the new position.
        self.cwin.mvwin(self.ulcrow, self.ulccol)

    def get_left_edge_col(self):
        """Returns the column value of the leftmost
        outside edge of this Window, in the parent Window's
        row and column coordinates.
        """
        return self.ulccol

    def get_right_edge_col(self):
        """Returns the column value of the rightmost
        outside edge of this Window, in the parent Window's
        row and column coordinates.
        """
        return self.ulccol + self.ncols

    def get_top_edge_row(self):
        """Returns the row value of the topmost outside
        edge of this Window, in the parent Window's
        row and column coordinates.
        """
        return self.ulcrow

    def get_bottom_edge_row(self):
        """Returns the row value of the bottommost
        outside edge of this Window, in the parent Window's
        row and column coordinates.
        """
        return self.ulcrow + self.nrows


class NewWindow(Window):
    """Encapsulates the behavior of a curses newwindow. These
    do NOT share the same buffer space as their parent window, so
    writing to a NewWindow will not change anything in a parent
    Window. They can also exist outside the boundaries of other
    curses window objects. Thus NewWindows can be useful for popup
    or overlay-type windows.
    """

    def __init__(self, parent, nrows, ncols, ulcrow, ulccol, title=None):
        super().__init__(parent, nrows, ncols, title)
        self.ulcrow = ulcrow
        self.ulccol = ulccol
        self.parent = parent

        # A curses newwindow has no parent window so does not need
        # to be constrained.
        self.cwin = curses.newwin(self.nrows, self.ncols, self.ulcrow, self.ulccol)

    # Probably not needed but here for completeness anyway.
    def __del__(self):
        if self.cwin is not None:
            del self.cwin

    def move(self, row, col):
        """Moves this NewWindow to a new row and column position.
        The values are clamped to remain inside the parent window.
        """
        self.ulcrow = self.parent.constrain_row(row)
        self.ulccol = self.parent.constrain_col(col)

        # Update the curses newwindow with the new position.
        self.cwin.mvwin(self.ulcrow, self.ulccol)

    def get_left_edge_col(self):
        """Returns the column value of the leftmost
        outside edge of this Window, in the parent Window's
        row and column coordinates.
        """
        return self.ulccol

    def get_right_edge_col(self):
        """Returns the column value of the rightmost
        outside edge of this Window, in the parent Window's
        row and column coordinates.
        """
        return self.ulccol + self.ncols

    def get_top_edge_row(self):
        """Returns the row value of the topmost outside
        edge of this Window, in the parent Window's
        row and column coordinates.
        """
        return self.ulcrow

    def get_bottom_edge_row(self):
        """Returns the row value of the bottommost
        outside edge of this Window, in the parent Window's
        row and column coordinates.
        """
        return self.ulcrow + self.nrows

    def _constrain(self):
        """Since NewWindows do not need to exist inside of
        another Window, they do not need to be constrained
        """
        return True


class EditDialog(NewWindow):
    """Encapsulates the behavior of temporary, popup dialog Window
    used to modify the data displayed in a Textfield.

    Given its parent Window, a prompt string, and a callback function
    that will save the new value to the appropriate variable, this
    class creates, maintains, and closes the dialog Window when
    the user is done.

    The default conversion method convert_to_int() returns an int
    value. You can replace that with others, for instance to convert
    to float or just return the text string itself.

    Similarly, you can also replace the dialog's default validator
    callback routine (which by default accepts any value) with your
    own validator routine, in order to constrain the user's input
    however you need.
    """

    def __init__(self, parent, prompt, save_cb=None):
        # Initialize this dialog Window instance.
        #
        # Note that in this case we won't actually call the dialog
        # Window's super().__init__() method until it is time to
        # actually open the dialog Window. This is required so that
        # the dialog will appear on top of all other existing Windows
        # at the time it is opened.
        self.parent = parent
        self.prompt = prompt

        # Set safe defaults for the dialog's callback routines.
        if save_cb is not None:
            self.saver = save_cb
        else:
            self.saver = self.default_save_cb

        self.converter = self.convert_to_int
        self.validator = self.default_validator

        # Since the NewWindow class references self.cwin in its
        # __del__() method, but an EditDialog will only call the
        # NewWindow's __init__() method if we actually open a
        # dialog Window, we need to initialize self.cwin here
        # just to avoid an AttributeError warning if we close
        # the program without ever actually opening the dialog.
        self.cwin = None

    def _build_dialog(self):
        """Creates and places the Textfields needed for
        this dialog Window.  Override this method if
        you want to display a dialog differently.
        """
        # Create and place Textfields for the prompt,
        # the edit field, and the status message areas.
        row = self.get_first_row()
        col = self.get_first_col()

        self.promptfield = Textfield(row, col)
        self.promptfield.write(self.prompt)
        row += self.promptfield.get_required_rows()

        self.editfield = Textfield(row, col)
        # Reserve a blank line for user input
        self.editfield.write("")
        row += self.editfield.get_required_rows()

        self.stsfield = Textfield(row, col)
        self.stsfield.write("Press <Enter> to submit")

        # Add the Textfields to the dialog Window
        self.add_field(self.promptfield)
        self.add_field(self.editfield)
        self.add_field(self.stsfield)

        # Now that we have the contents of each Textfield defined
        # we can permanently resize this dialog Window to contain
        # all of them. So figure out the new nrows and ncols we
        # need.
        nrows = row + self.stsfield.get_required_rows()

        # Since row starts at get_first_row() we only need
        # to account for the bottom border (if any).
        nrows += self.border_height if self.has_border else 0

        # Find the length of the longest dialog text line.
        ncols = self.promptfield.get_required_cols()
        ncols = max(ncols, self.stsfield.get_required_cols())

        # ncols is currently just the space needed for the longest
        # dialog text. We still need to account for both the left
        # and right borders (if any).
        ncols += 2 * self.border_width if self.has_border else 0

        self.resize(nrows, ncols, True)

        # Now recenter this resized dialog Window.
        ulcrow = self.parent.get_center_row() - int(nrows / 2)
        ulccol = self.parent.get_center_col() - int(ncols / 2)
        self.move(ulcrow, ulccol)

    def _setup_dialog_keys(self):
        """Configures a KeyResponse instance to handle
        user keyhits for this dialog Window.  This default
        method will handle integer values only. Override
        this method if you want to handle user keyhits
        differently.
        """
        # The edit KeyResponse may need to be different
        # for different edit types (e.g. int, float, enum, text)
        key_list = [
            curses.KEY_BACKSPACE,
            # curses.KEY_DC, # DELETE key
            ord("-"),
        ]
        edit_keys = KeyResponse("Edit", key_list)
        edit_keys.set_filter(curses.ascii.isdigit)
        self.add_key(edit_keys)

        def _kr_edit_int(keyhit):
            # Write digits and minus signs into the Textfield
            curtext = self.editfield.get_text()
            if curses.ascii.isdigit(keyhit) or keyhit == ord("-"):
                curtext += chr(keyhit)
            elif keyhit == curses.KEY_BACKSPACE:
                curtext = curtext[:-1]
            self.editfield.write(curtext)

        edit_keys.bind(_kr_edit_int)

        # The ENTER key now should end editing the
        # Textfield.
        self.parent.get_key("enter").bind(self._kr_end_field_edit)

        def _kr_do_nothing(_):
            # A key response routine that does nothing. Use
            # this to temporarily suppress a key's behavior.
            pass

        # Here, the TAB key should do nothing
        self.parent.get_key("tab").bind(_kr_do_nothing)

        # The ESC should quit without changing
        # anything.
        self.parent.get_key("esc").bind(self._kr_quit_field_edit)

    def kr_begin_field_edit(self, _):
        """This key response routine begins an edit
        session on the currently selected Textfield.

        This is the only dialog key response routine
        that needs to be publicly accessible. The
        others are only referenced internally by the
        dialog Window instance itself.
        """
        child = self.parent.get_selected_child()
        sf = child.get_selected_field()
        sf.dialog.begin()

    def _kr_end_field_edit(self, _):
        # Calls the validator callback (if any) and
        # the saver callback to write the result
        # to the Textfield's target variable. Then
        # calls _quit() to close the dialog Window.
        self._end()

    def _kr_quit_field_edit(self, _):
        # Cleans up and removes the dialog Window
        self._quit()

    def convert_to_int(self):
        """Tries to convert the editfield text
        into an integer value.
        """
        try:
            result = int(self.editfield.get_text())
            return result
        except ValueError:
            self.stsfield.write("Not an integer!")
            return None

    def begin(self):
        """Begins an edit session on the currently
        selected Textfield.
        """
        # The _build_dialog() method will resize and reposition the
        # curses new window after it is created so these size and
        # position values are arbitrary.
        nrows = 10
        ncols = 20
        ulcrow = self.parent.get_center_row() - int(nrows / 2)
        ulccol = self.parent.get_center_col() - int(ncols / 2)

        # Create the dialog Window and add it to its parent
        super().__init__(self.parent, nrows, ncols, ulcrow, ulccol, "Edit")

        # Populate the dialog Window and configure how
        # it will respond to user keyhits.
        self._build_dialog()
        self._setup_dialog_keys()

        # Save the previously selected Window so that we can
        # restore it when the dialog is finished.  Then select
        # this dialog Window to bring the user focus here.
        self.prior_selection = self.parent.get_selected_child()
        self.parent.select_child(self)

    def default_validator(self, result):
        """A simple input validation routine for user input."""

        if result is not None:
            return True
        else:
            return False

    def default_save_cb(self, result):
        """A simple callback for saving validated user input."""

        print("Entered {0}".format(result))

    def _end(self):
        # Read and process the user input
        result = self.converter()

        # If conversion was successful and
        # the result is acceptable, save it
        # and close the dialog.
        if self.validator(result):
            self.saver(result)
            self._quit()

    def _quit(self):
        # Restore the previous key bindings
        self.parent.get_key("enter").unbind()
        self.parent.get_key("tab").unbind()
        self.parent.get_key("esc").unbind()

        # Restore the previous selection
        self.parent.select_child(self.prior_selection)

        # Remove this dialog Window
        self.parent.remove_child(self)


class FloatDialog(EditDialog):
    """Encapsulates the behavior of temporary, popup dialog Window
    used to modify the float value displayed in a Textfield.

    Given its parent Window, a prompt string, and a callback function
    that will save the new string to the appropriate variable, this
    class creates, maintains, and closes the dialog Window when
    the user is done.
    """

    def __init__(self, parent, prompt, save_cb=None):
        super().__init__(parent, prompt, save_cb)

        self.converter = self.convert_to_float

    def _setup_dialog_keys(self):
        """Override's the parent method to edit floating point
        values.
        """
        # The edit KeyResponse may need to be different
        # for different edit types (e.g. int, float, enum, text)
        key_list = [
            curses.KEY_BACKSPACE,
            # curses.KEY_DC, # DELETE key
            ord("-"),
            ord("."),
        ]
        edit_keys = KeyResponse("Edit", key_list)
        edit_keys.set_filter(curses.ascii.isdigit)
        self.add_key(edit_keys)

        def _kr_edit_float(keyhit):
            # Write digits, decimal points and minus signs into the Textfield
            curtext = self.editfield.get_text()
            if curses.ascii.isdigit(keyhit) or keyhit == ord("-") or keyhit == ord("."):
                curtext += chr(keyhit)
            elif keyhit == curses.KEY_BACKSPACE:
                curtext = curtext[:-1]
            self.editfield.write(curtext)

        edit_keys.bind(_kr_edit_float)

        # The ENTER key now should end editing the
        # Textfield.
        self.parent.get_key("enter").bind(self._kr_end_field_edit)

        # The TAB key should do nothing
        def _kr_do_nothing(_):
            pass

        self.parent.get_key("tab").bind(_kr_do_nothing)

        # The ESC should quit without changing
        # anything.
        self.parent.get_key("esc").bind(self._kr_quit_field_edit)

    def convert_to_float(self):
        """Tries to convert the editfield text
        into a floating point value.
        """
        try:
            result = float(self.editfield.get_text())
            return result
        except ValueError:
            self.stsfield.write("Not a float value!")
            return None


class TextDialog(EditDialog):
    """Encapsulates the behavior of temporary, popup dialog Window
    used to modify the text string displayed in a Textfield.

    Given its parent Window, a prompt string, and a callback function
    that will save the new string to the appropriate variable, this
    class creates, maintains, and closes the dialog Window when
    the user is done.
    """

    def __init__(self, parent, prompt, save_cb=None):
        super().__init__(parent, prompt, save_cb)

        self.converter = self.convert_to_text

    def _setup_dialog_keys(self):
        """Override's the parent method to allow all
        ASCII characters.
        """
        key_list = [curses.KEY_BACKSPACE]
        edit_keys = KeyResponse("Edit", key_list)
        edit_keys.set_filter(curses.ascii.isgraph)
        self.add_key(edit_keys)

        def _kr_edit_text(keyhit):
            curtext = self.editfield.get_text()
            if curses.ascii.isgraph(keyhit):
                curtext += chr(keyhit)
            elif keyhit == curses.KEY_BACKSPACE:
                curtext = curtext[:-1]
            self.editfield.write(curtext)

        edit_keys.bind(_kr_edit_text)

        # The ENTER key now should end editing the
        # Textfield.
        self.parent.get_key("enter").bind(self._kr_end_field_edit)

        # The TAB key should do nothing
        def _kr_do_nothing(_):
            pass

        self.parent.get_key("tab").bind(_kr_do_nothing)

        # The ESC should quit without changing
        # anything.
        self.parent.get_key("esc").bind(self._kr_quit_field_edit)

    def convert_to_text(self):
        """Simply returns the Editfield text string"""
        return self.editfield.get_text()


class EnumDialog(EditDialog):
    """Encapsulates the behavior of temporary, popup dialog Window
    used to modify a Textfield displaying an enumerated constant. One
    of the constructor's arguments is the enum class itself. The
    dialog displays all members of the enum and allows the user to
    select any member. The dialog's conversion method then returns
    that selected member of the given enum class.
    """

    def __init__(self, parent, enum_class, prompt, save_cb=None):
        super().__init__(parent, prompt, save_cb)

        self.enum_class = enum_class
        self.converter = self.convert_to_enum

    def _build_dialog(self):
        """Overrides the parent's _build_dialog() method to
        display and select among a set of enumerated constants.
        """
        # Create and place Textfields for the prompt,
        # the edit field, and the status message areas.
        row = self.get_first_row()
        col = self.get_first_col()

        self.promptfield = Textfield(row, col)
        self.promptfield.write(self.prompt)
        self.add_field(self.promptfield)
        row += self.promptfield.get_required_rows()

        # Create and place a Textfield for each possible
        # enum value.
        items = len(self.enum_class)
        fields = []
        members = list(self.enum_class)
        indent = col + 2
        maxlen = 0

        for i in range(items):
            fields.append(Textfield(row + i, indent))
            name = members[i].name
            fields[i].write(name)
            fields[i].set_selectable(True)
            maxlen = max(maxlen, len(name))
            self.add_field(fields[i])
        row += i + 1

        self.stsfield = Textfield(row, col)
        self.stsfield.write("Press <Enter> to submit")
        self.add_field(self.stsfield)

        # Now that we have the contents of the dialog Window defined
        # we can permanently resize it to contain all of them.
        nrows = row + self.stsfield.get_required_rows()

        # Since the row starts at get_first_row() we only need
        # to account for the bottom border (if any).
        nrows += self.border_height if self.has_border else 0

        # Find the length of the longest dialog text line.
        ncols = self.promptfield.get_required_cols()
        ncols = max(ncols, self.stsfield.get_required_cols())
        ncols = max(ncols, maxlen + indent)

        # ncols is currently just the space needed for the longest
        # dialog text. We still need to account for both the left
        # and right borders (if any).
        ncols += 2 * self.border_width if self.has_border else 0

        self.resize(nrows, ncols, True)

        # Now recenter this resized dialog Window.
        ulcrow = self.parent.get_center_row() - int(nrows / 2)
        ulccol = self.parent.get_center_col() - int(ncols / 2)
        self.move(ulcrow, ulccol)

    def _setup_dialog_keys(self):
        """Overrides the parent method to handle keyhits for
        enum Textfields.
        """
        # There is no editing to be done with an enum Textfield
        # (only selection among the choices), so no keys are
        # needed for editing it.
        #
        # The ENTER key now should end editing the enum Textfield.
        self.parent.get_key("enter").bind(self._kr_end_field_edit)

        def _kr_select_next_enum(_):
            # This key response routine finds the currently
            # selected Textfield.  If found it unselects it,
            # finds the next selectable Textfield, and selects
            # that one.  Returns the newly selected Textfield,
            # or None on failure.
            sf = self.get_selected_field()
            if sf != None:
                sf.unselect()
                n = len(self.get_textfields())
                for i in range(n):
                    # Note: get_next_field() ignores
                    # titlefields.
                    nxtf = self.get_next_field(sf)
                    sf = self.select_field(nxtf)
                    if sf != None:
                        return sf
                    sf = nxtf
            return None

        # The TAB key should select the next enum Textfield
        self.parent.get_key("tab").bind(_kr_select_next_enum)

        # The ESC should quit without changing anything.
        self.parent.get_key("esc").bind(self._kr_quit_field_edit)

    def begin(self):
        """Begins an edit session dialog for the currently
        selected enum Textfield.
        """
        # Begin the normal dialog first. This will open the
        # dialog Window and select it, but it does not select
        # any Textfields inside that dialog Window.
        super().begin()

        # If no Textfields are currently selected, this will
        # select the first one.
        self.get_selected_field()

        # Make the currently selected Textfield visible.
        self.show_selected_field(True)

    def convert_to_enum(self):
        """Tries to convert the selected Textfield
        into an enumerated constant.
        """
        # Find the currently selected enum Textfield
        enum_name = self.get_selected_field().get_text()

        # Try to convert it to an enum value
        try:
            return self.enum_class[enum_name]
        except KeyError:
            self.stsfield.write("Not a member!")
            return None


class ListDialog(EditDialog):
    """Encapsulates the behavior of temporary, popup dialog Window
    used to modify a Textfield displaying an element of a list of
    strings. One of the constructor's arguments is the list. The
    dialog displays all list elements and allows the user to select
    any one element. The dialog's conversion method then returns
    the index value of that selected element.
    """

    def __init__(self, parent, string_list, prompt, save_cb=None):
        super().__init__(parent, prompt, save_cb)

        self.string_list = string_list
        self.converter = self.convert_to_index

    def _build_dialog(self):
        """Overrides the parent's _build_dialog() method to
        display and select among a set of enumerated constants.
        """
        # Create and place Textfields for the prompt,
        # the edit field, and the status message areas.
        row = self.get_first_row()
        col = self.get_first_col()

        self.promptfield = Textfield(row, col)
        self.promptfield.write(self.prompt)
        self.add_field(self.promptfield)
        row += self.promptfield.get_required_rows()

        # Create and place a Textfield for each possible
        # list element.
        items = len(self.string_list)
        fields = []
        # members = list(self.enum_class)
        indent = col + 2
        maxlen = 0

        for i in range(items):
            fields.append(Textfield(row + i, indent))
            name = self.string_list[i]
            fields[i].write(name)
            fields[i].set_selectable(True)
            maxlen = max(maxlen, len(name))
            self.add_field(fields[i])
        row += i + 1

        self.stsfield = Textfield(row, col)
        self.stsfield.write("Press <Enter> to submit")
        self.add_field(self.stsfield)

        # Now that we have the contents of the dialog Window defined
        # we can permanently resize it to contain all of them.
        nrows = row + self.stsfield.get_required_rows()

        # Since the row starts at get_first_row() we only need
        # to account for the bottom border (if any).
        nrows += self.border_height if self.has_border else 0

        # Find the length of the longest dialog text line.
        ncols = self.promptfield.get_required_cols()
        ncols = max(ncols, self.stsfield.get_required_cols())
        ncols = max(ncols, maxlen + indent)

        # ncols is currently just the space needed for the longest
        # dialog text. We still need to account for both the left
        # and right borders (if any).
        ncols += 2 * self.border_width if self.has_border else 0

        self.resize(nrows, ncols, True)

        # Now recenter this resized dialog Window.
        ulcrow = self.parent.get_center_row() - int(nrows / 2)
        ulccol = self.parent.get_center_col() - int(ncols / 2)
        self.move(ulcrow, ulccol)

    def _setup_dialog_keys(self):
        """Overrides the parent method to handle keyhits for
        list Textfields.
        """
        # There is no editing to be done with a list Textfield
        # (only selection among the choices), so no keys are
        # needed for editing it.
        #
        # The ENTER key now should end editing the list Textfield.
        self.parent.get_key("enter").bind(self._kr_end_field_edit)

        def _kr_select_next_element(_):
            # This key response routine finds the currently
            # selected Textfield.  If found it unselects it,
            # finds the next selectable Textfield, and selects
            # that one.  Returns the newly selected Textfield,
            # or None on failure.
            sf = self.get_selected_field()
            if sf != None:
                sf.unselect()
                n = len(self.get_textfields())
                for i in range(n):
                    # Note: get_next_field() ignores
                    # titlefields.
                    nxtf = self.get_next_field(sf)
                    sf = self.select_field(nxtf)
                    if sf != None:
                        return sf
                    sf = nxtf
            return None

        # The TAB key should select the next list Textfield
        self.parent.get_key("tab").bind(_kr_select_next_element)

        # The ESC should quit without changing anything.
        self.parent.get_key("esc").bind(self._kr_quit_field_edit)

    def begin(self):
        """Begins an edit session dialog for the currently
        selected list Textfield.
        """
        # Begin the normal dialog first. This will open the
        # dialog Window and select it, but it does not select
        # any Textfields inside that dialog Window.
        super().begin()

        # If no Textfields are currently selected, this will
        # select the first one.
        self.get_selected_field()

        # Make the currently selected Textfield visible.
        self.show_selected_field(True)

    def convert_to_index(self):
        """Tries to convert the selected Textfield
        into an index into the dialog's list of strings.
        """
        # Find the currently selected list Textfield
        list_name = self.get_selected_field().get_text()

        # Try to convert it to an index value
        try:
            return self.string_list.index(list_name)
        except KeyError:
            self.stsfield.write("Not in list!")
            return None


class PadWindow(Window):
    """Encapsulates the behavior of a curses padwindow. PadWindows
    are much like NewWindows except that they can have a size larger
    than what is visible on screen. You can scroll the pad under the
    visible window (the "viewport") to reveal hidden portions of the
    pad.

    Use PadWindows to display things like status histories and log
    streams.

    Note that simply drawing a border around a PadWindow would not
    look the same as with other window types. The border would apply
    to the curses padwindow, not the viewport. So portions of the
    border will only be visible if they happen to be within the
    PadWindow's viewport.  Thus borders are usually not appropriate
    for the pad itself.

    To actually give the viewport a border we need to first create
    another type of window with a border, then fill it entirely with
    the PadWindow's viewport.

    We do that here with a SubWindow. Its only purpose is to provide
    border, title and selection behaviors to the viewport of this
    PadWindow.
    """

    def __init__(
        self, parent, nrows, ncols, ulcrow, ulccol, lrcrow, lrccol, title=None
    ):
        # Create a SubWindow for the viewport first. This encloses
        # the PadWindow's viewport with a border and a title, making
        # PadWindows look much like the other Window subclasses. This
        # SubWindow is not used for anything other than maintaining a
        # visible border around the PadWindow's viewport.
        vprows = lrcrow - ulcrow + 1
        vpcols = lrccol - ulccol + 1
        self.vpwin = SubWindow(parent, vprows, vpcols, ulcrow, ulccol, title)

        # Now create the PadWindow itself, as a child of the viewport
        # SubWindow. This overlays the visible contents of the curses
        # padwindow on top of the viewport SubWindow.
        super().__init__(self.vpwin, nrows, ncols)
        self.padrow = 0
        self.padcol = 0
        self.ulcrow = ulcrow + 1
        self.ulccol = ulccol + 1
        self.lrcrow = lrcrow
        self.lrccol = lrccol
        self.parent = self.vpwin
        self.has_border = False
        self.selected = False

        # A curses pad window can be any size so
        # it should not need to be constrained when
        # created.
        self.cwin = curses.newpad(nrows, ncols)

        # PadWindows are scrollable by default
        self.cwin.scrollok(True)

    def set_selectable(self, flag: bool = True):
        """Override the parent method to apply the
        selectable flag to the PadWindow's viewport
        Window instead.
        """
        self.vpwin.selectable = flag

    def select(self):
        """Override the parent method to select
        the PadWindow's viewport Window instead.
        """
        if self.vpwin.selectable:
            self.vpwin.selected = True

    def unselect(self):
        """Override the parent method to unselect the
        PadWindow's viewport Window instead.
        """
        self.vpwin.selected = False

    def move(self, row, col):
        """Moves this PadWindow's viewport to a new row and
        column position. The values are clamped to remain
        inside the parent window.
        """
        self.ulcrow = self.parent.constrain_row(row)
        self.ulccol = self.parent.constrain_col(col)

        # Move the SubWindow instance that contains the
        # curses padwindow's viewport.
        self.vpwin.cwin.mvwin(self.ulcrow, self.ulccol)

    def get_left_edge_col(self):
        """Returns the column value of the leftmost
        outside edge of this Window, in the parent Window's
        row and column coordinates.
        """
        return self.ulccol

    def get_right_edge_col(self):
        """Returns the column value of the rightmost
        outside edge of this Window, in the parent Window's
        row and column coordinates.
        """
        return self.lrccol

    def get_top_edge_row(self):
        """Returns the row value of the topmost outside
        edge of this Window, in the parent Window's
        row and column coordinates.
        """
        return self.ulcrow

    def get_bottom_edge_row(self):
        """Returns the row value of the bottommost
        outside edge of this Window, in the parent Window's
        row and column coordinates.
        """
        return self.lrcrow

    # PadWindows don't get a border; that will apply
    # to their viewport SubWindow instead.
    def draw_border(self):
        """Overrides the default Window object behavior"""
        pass

    def scroll_up(self):
        """Scrolls the PadWindow's pad contents up within
        the viewport.
        """
        maxrow = self.nrows - 1
        newrow = self.padrow + 1
        self.padrow = newrow if newrow < maxrow else maxrow

    def scroll_down(self):
        """Scrolls the PadWindow's pad contents down within
        the viewport.
        """
        newrow = self.padrow - 1
        self.padrow = newrow if newrow > 0 else 0

    def scroll_left(self):
        """Scrolls the PadWindow's pad contents left within
        the viewport.
        """
        maxcol = self.ncols - 1
        newcol = self.padcol + 1
        self.padcol = newcol if newcol < maxcol else maxcol

    def scroll_right(self):
        """Scrolls the PadWindow's pad contents right within
        the viewport.
        """
        newcol = self.padcol - 1
        self.padcol = newcol if newcol > 0 else 0

    def _constrain(self):
        """PadWindows are different from other Windows in
        that their curses window is a viewport onto a pad. The
        pad itself does not ever need to be constrained. So
        we override the base method here to do nothing. All
        of the actual constraint of the viewport is handled
        in the PadWindow's refresh() method.
        """
        return True

    def add_attrs(self, attrs):
        """Overrides the parent's method to add
        the same attributes to the viewport SubWindow
        that contains this PadWindow.
        """
        self.vpwin.add_attrs(attrs)
        super().add_attrs(attrs)

    def refresh(self):
        """Overrides the parent's method to transfer
        this PadWindow viewport's content to the curses
        virtual screen, constrained by the parent's
        current row & column limits.
        """
        # Get the current row and column limits of the
        # parent of the viewport Subwindow.
        #
        # We have to skip the viewport SubWindow and
        # get the limits from its parent.
        row_limit = self.parent.parent.get_last_row()
        col_limit = self.parent.parent.get_last_col()

        # Get the border width and height for the enclosing
        # viewport Subwindow, which normally will have a
        # border (that is its purpose). To make sure the
        # curses viewport does not overwrite those border
        # characters, we need to further reduce the parent
        # Window's limits by the size of those border
        # characters.
        bw = self.parent.border_width if self.parent.has_border else 0
        bh = self.parent.border_height if self.parent.has_border else 0
        row_limit -= bh
        col_limit -= bw

        # Don't bother to refresh if not even the upper left corner
        # of the curses padwindow viewport will be visible.
        if self.ulcrow >= row_limit or self.ulccol >= col_limit:
            return

        # Otherwise, limit the lower right corner of the curses
        # padwindow's viewport, again making sure it does not
        # overwrite the border characters when they are present.
        lrcrow = min(self.lrcrow - bw, row_limit)
        lrccol = min(self.lrccol - bh, col_limit)

        # A curses padwindow refresh requires all 6 parameters
        self.cwin.noutrefresh(
            self.padrow, self.padcol, self.ulcrow, self.ulccol, lrcrow, lrccol
        )


class Display(Window):
    """Encapsulates the behavior of a curses top level display window.
    The Display Window never has a parent Window object.
    """

    def __init__(self, stdscr, title=None):
        # Get the current dimensions of this entire display window
        nrows, ncols = stdscr.getmaxyx()
        super().__init__(None, nrows, ncols, title)
        self.cwin = stdscr

    def _constrain(self):
        # The top level Display Window has no parent so
        # cannot be constrained by one and is therefore always
        # visible. So this override method does nothing and always
        # returns True.
        return True

    def repaint(self):
        """Repaints the Display Window and all child Windows at
        the Display Window's current size.
        """
        # Get the current dimensions of this entire Display Window
        self.nrows, self.ncols = self.cwin.getmaxyx()

        # Repaint this Window and all its children onto the curses
        # virtual display screen.
        super().repaint()

        # Now transfer the curses virtual screen to the physical
        # display.
        curses.doupdate()


class TextBuffer:
    """A generic Text buffer used by the CursesUI class to
    temporarily replace stdout and stderr. We need to redirect
    these to prevent anything from writing to the actual screen
    while curses has control of the display screen.

    This defaults to a maximum of the most recent 30 lines of
    text. But you can change this maximum at any time with the
    set_maxlines() method.
    """

    def __init__(self, maxlines=30):
        self.set_maxlines(maxlines)
        self.clear()

    def clear(self):
        """Empty the text buffer."""
        self.text = ""

    def write(self, newtxt):
        """Adds one or more lines to the text buffer. The
        total number of lines in the buffer is limited to
        maxlines which defaults to 30.  When the limit is
        reached, the oldest lines will be dropped first.
        """
        self.text += newtxt

        # Because of the newline character, we need to add
        # one here to maxlines to be able to keep at most
        # maxlines of text in the buffer.
        self.text = "\n".join(self.text.split("\n")[-(self.maxlines + 1) :])

    def read(self, start=0, end=-1):
        """Reads (from start to end) lines from the text buffer.
        If start and end are not specified, this will return the
        entire buffer contents.
        """
        return "\n".join(self.text.split("\n")[start:end])

    def get_length(self):
        """Returns the total number of characters in the buffer."""
        return len(self.text)

    def get_maxlines(self):
        """Returns the maximum number of lines that can be held
        in the buffer. When the maximum is reached, older lines
        will be dropped. Default is 30.
        """
        return self.maxlines

    def set_maxlines(self, newmax):
        """Change the maximum number of lines that can be held
        in the buffer. The minimum allowed value is clamped to 1.
        """
        self.maxlines = max(newmax, 1)


class CursesUI:
    """Creates and maintains the user interface for a text-mode
    windowed console application using the Python curses and
    asyncio libraries. Regularly repaints the screen and responds
    to user input until the application ends. On exit it restores
    normal console display and keyboard behavior before returning
    to the command line.
    """

    def __init__(self, display_builder=None, response_builder=None, title=None):
        self.display = None
        self.has_colors = None
        self.can_change_color = None
        self.title = title
        self.done: bool = False
        self.loglevel = logging.ERROR
        self.old_stdout = None
        self.old_stderr = None
        self.stdout_bfr = None
        self.coroutines = []

        # Install the display and response builder routines
        if display_builder is not None:
            self.set_display_builder(display_builder)
        else:
            self.set_display_builder(self.setup_default_display)
        if response_builder is not None:
            self.set_response_builder(response_builder)
        else:
            self.set_response_builder(self.setup_default_responses)

    def add_title(self, title):
        """Adds a title to the top-level display Window."""
        self.title = title

    def kr_done_with_ui(self, _):
        """This key response routine ends the CursesUI
        session.
        """
        self.done = True

    def get_display(self):
        """Returns the top-level Display Window for this
        CursesUI instance.
        """
        return self.display

    def set_display_builder(self, display_builder):
        """Installs the routine that your CursesUI instance
        will call to set up its initial display Window. Your
        routine will get passed a reference to your CursesUI
        instance.

        You can use this method instead of providing the display
        builder routine to the CursesUI constructor. If you do
        use this method, be sure to call it before you call the
        CursesUI run() method.
        """
        self.display_builder = display_builder

    def set_response_builder(self, response_builder):
        """Installs the routine that your CursesUI instance
        will call to set up its initial key responses. Your
        routine will get passed a reference to your CursesUI
        instance.

        You can use this method instead of providing the key
        response builder routine to the CursesUI constructor.
        If you do use this method, be sure to call it before
        you call the CursesUI run() method.
        """
        self.response_builder = response_builder

    def add_coroutine(self, coroutine):
        """Add an asynchronous coroutine for this CursesUI
        session to run concurrently. You can add coroutines
        at any time during the CursesUI session.

        Each asynchronous coroutine must be defined with
        the "async" prefix, as in:

        async def my_coroutine(self):

        The coroutine itself may be a routine that yields
        but ultimately ends.  Or it may be a (possibly
        infinite) loop wherein you call at least one
        asynchronously yielding routine such as sleep().
        For example:

        while True:
            do_something_useful()
            await asyncio.sleep(0.1)

        Note: you can set a sleep delay of zero in order
        to still yield, but do so with minimal delay.

        If your coroutine does not have both the async
        prefix and the await call, then your coroutine
        may never yield back control to your CursesUI
        instance.
        """
        self.coroutines.append(coroutine)

    def _start_coroutines(self):
        # Asynchronously start any coroutine found in the
        # coroutine list.
        #
        # We don't need to save the task object returned
        # from each call to asyncio.create_task() because
        # we assume each will run to completion (or forever);
        # we will not need to cancel or otherwise interact
        # directly with those task objects.  Normal Python
        # garbage collection will automatically terminate any
        # still running when this CursesUI instance ends.
        for coroutine in self.coroutines:
            asyncio.create_task(coroutine())
            self.coroutines.remove(coroutine)

    def initialize_loglevel(self, loglevel):
        """Set up the default log reporting level for this
        CursesUI instance.
        """
        self.loglevel = loglevel

    def _setup_logging(self):
        # Set up a logger to use for this module.
        #
        # This turns out to be quite tricky, since the logging
        # library is designed to make sure log messages get seen
        # with minimal effort.  This means that the library
        # will try very hard to issue log messages to stderr,
        # even if you don't want it to. And we don't want anything
        # going to the console during a curses window session
        # since any such output to the screen will corrupt the
        # windows that curses maintains. So beware, and tread
        # lightly!
        #
        # When the library has created its own handler behind your
        # back, the evidence will typically be either that
        # your curses windows gets corrupted by log messages or
        # that you see duplicate log messages in text buffer
        # dumps.
        #
        # After much testing, what seems to work best here is
        # to explicitly set up two logging StreamHandlers; one
        # that sends log messages to stderr (just like logging
        # will do by default) and another that sends log messages
        # to a text buffer instead.  We switch to the buffered
        # handler just before the curses window session starts,
        # and then switch back to the stderr handler when curses
        # is done using the console screen.
        #
        # The main reason we explicitly set up the stderr handler
        # (instead of letting the logging library create one by
        # default) is that we get full control of the handler we
        # create and therefore the ability to remove it cleanly
        # and reliably, when we need to prevent any logging to
        # the screen.
        #
        # Finally, note that your application should NOT EVER call
        # logging.BasicConfig(); it will break this redirection!
        # Your app can still call logging.getlogger(), change the
        # log level, and write log messages as you normally would.

        self.sh = logging.StreamHandler(sys.stderr)
        self.formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")
        self.sh.setFormatter(self.formatter)
        log.addHandler(self.sh)
        log.setLevel(self.loglevel)
        log.debug("Logging initialized for this module")
        log.debug("Total handlers = {0}".format(len(log.handlers)))

        # Now redirect all logging output to the buffer.
        self._redirect_logging()

    def _redirect_logging(self):
        # In order to prevent log output from corrupting
        # the displayed curses windows, we need to redirect
        # log output to a text buffer which we can display
        # in its own curses window, and/or dump to the
        # console after the curses windowing session has
        # ended.
        self.stdout_bfr = TextBuffer()
        self.bh = logging.StreamHandler(self.stdout_bfr)
        self.bh.setFormatter(self.formatter)

        # Always add a new handler before removing the
        # previous one. Otherwise if the library sees that
        # there are no handlers installed, it may sneak
        # in and install one behind your back.
        log.addHandler(self.bh)
        log.removeHandler(self.sh)

        log.debug("stdout_bfr length = {0}".format(self.stdout_bfr.get_length()))
        log.debug("Total handlers = {0}".format(len(log.handlers)))
        log.debug("Logging redirected to buffer")

    def _restore_logging(self):
        # Stop logging to the text buffer and send log messages
        # to stderr instead. Add the new handler before removing
        # the old one.
        log.debug("Restoring logging to stderr")
        log.addHandler(self.sh)
        log.removeHandler(self.bh)
        log.debug("Restored logging to stderr")

    def _redirect_console(self):
        # Here we redirect any stderr or stdout writes
        # to our text buffer. This alone is not
        # sufficient to redirect log messages though,
        # because the logging library grabs its own
        # copy of sys.stderr when it installs its handler.
        # This is why we need to explicity set up
        # and manage our own handlers.
        log.debug("Capturing log messages")

        # Save the current stdout and stderr console output routines
        self.old_stdout = sys.stdout
        self.old_stderr = sys.stderr

        # Send any console output during the curses session to our
        # text buffer instead.
        sys.stdout = self.stdout_bfr
        sys.stderr = self.stdout_bfr
        log.debug("Capturing stdout and stderr")
        log.debug("stdout_bfr length = {0}".format(self.stdout_bfr.get_length()))

    def _restore_console(self):
        # Restore stdout and stderr and the logging handler too.
        log.debug("stdout_bfr length = {0}".format(self.stdout_bfr.get_length()))
        log.debug("Done capturing log messages")
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr
        log.debug("stdout_bfr length = {0}".format(self.stdout_bfr.get_length()))
        log.debug("Restored stdout and stderr")
        self._restore_logging()

        # If there is anything in the buffer, dump it to the console now.
        bfr_length = self.stdout_bfr.get_length()
        log.debug("stdout_bfr length = {0}".format(bfr_length))
        if bfr_length > 0:
            log.info("----Dumping log buffer to stdout----")
            sys.stdout.write(self.stdout_bfr.read())
            # Add a newline after the dump.
            sys.stdout.write("\n")
            log.info("----Log dump complete----")

    async def _event_loop(self):
        # Run the CursesUI event loop asynchronously.
        # so that other processes can also run concurrently.
        while not self.done:
            # I'm not exactly sure why, but if you try to start
            # the coroutine processes outside of this event loop
            # they will break the careful redirection of log
            # messages -- causing them to print directly to the
            # console screen instead of to the TextBuffer and
            # corrupting the curses display windows.
            #
            # We call this within the event loop so that you can
            # start new coroutine tasks at any time during the
            # CursesUI session.
            self._start_coroutines()

            # Repaint the display window and its contents,
            # then transfer that to the curses virtual screen.
            # Then repaint all child windows and transfer
            # each one, in order, to overlay onto the virtual
            # screen.  Finally, transfer the virtual screen
            # to the physical display screen.
            self.display.repaint()

            # Now read and process any new keyhits.
            #
            # Note: if the display window has changed
            # then curses will call refresh() on it
            # before getch(). An extra refresh should
            # not be a problem, but if it ever is, the
            # way to avoid it would be to call getch()
            # from a dummy window that you do not use
            # to display anything. Make sure echo is
            # off too!
            keyvalue = self.display.cwin.getch()

            # A keyvalue of curses.ERR means that no new
            # key has been pressed.  So just yield to other
            # async processes and then try again.
            if keyvalue == curses.ERR:
                # Note that a sleep time of 0 will still
                # yield, but with minimal delay. Or
                # increase the delay to 2 seconds if
                # during debug you need to slow down
                # the rate at which log messages get
                # generated.
                await asyncio.sleep(0.1)
                continue

            else:
                # Handle any other keyboard input.
                self.display._process_keyhit(keyvalue)

    def _run_wrapped_ui(self, stdscr):
        """Starts and and maintains the console UI until
        done. This method gets passed a curses stdscr object
        which is the top-level display window for the curses
        session.
        """
        # Now that curses is initialized, capture this
        # terminal's color support.
        self.has_colors = curses.has_colors()
        if self.has_colors:
            self.can_change_color = curses.can_change_color()
            self.total_color_numbers = curses.COLORS
            # Even though curses.COLOR_PAIRS can be as large as
            # 65535, any color pair number over 255 does not work
            # correctly.
            self.total_color_pairs = min(curses.COLOR_PAIRS, 255)
        else:
            self.can_change_color = False
            self.total_color_numbers = 1
            self.total_color_pairs = 1

        # Create a Display instance for the curses screen.
        self.display = Display(stdscr, self.title)

        # Set up the curses library defaults for user input.
        self.config_input()

        # Build the initial display and set up the initial
        # key responses. By default these will create simple
        # CursesUI demonstration applications.  Create and
        # install your own builder routines for your own
        # application UI. Each builder routine receives a
        # reference to your CursesUI instance.
        self.display_builder(self)
        self.response_builder(self)

        # Run the CursesUI event loop asynchronously, maintaining
        # the display and responding to user input until done.
        #
        # Running the loop asynchronously allows you to have other
        # async processes running concurrently with it, and
        # your UI instance can then both monitor and interact with
        # them. (The DemoProcess class is a very simple example of
        # this kind of asynchronous concurrent coroutine.)
        asyncio.run(self._event_loop())

    def run(self):
        """Sets up the proper environment, then runs the CursesUI
        instance until the user ends it. If there are unhandled
        (fatal) exceptions then this method will grab the Python
        traceback info and dump it to the console on exit.
        """
        # Explicitly set up our own stream handlers for logging.
        self._setup_logging()

        # Set up the UI session. The first priority is to prevent
        # stdout and stderr from writing to the console, as this
        # will corrupt any displayed curses windows.
        self._redirect_console()

        # Use curses.wrapper to handle curses startup and shutdown
        # cleanly. The wrapper creates the curses stdscr window
        # object and then passes it to _run_wrapped_ui().
        try:
            curses.wrapper(self._run_wrapped_ui)

        # Handle any exception type.
        except:
            # Python traceback stack dumps normally use their own
            # connection to the console. So to be able to see
            # traceback info on Python fatal errors, we need to
            # explicitly tell Python to send that dump to our
            # redirected stderr sink (i.e. the TextBuffer) instead.
            traceback.print_exc(file=sys.stderr)

        finally:
            # clean up before exit by restoring normal console
            # output and then dumping any buffered console output
            # to the screen.
            self._restore_console()

    def config_input(self):
        """Sets up defaults for user input. You probably
        won't need to change this, but if you do simply
        override it.
        """
        # Do not wait for keyhits (required!!)
        self.display.cwin.nodelay(True)

        # Turn off the cursor (important!)
        # (TODO: throws an exception on simple terminals)
        curses.curs_set(0)

        # Enable support for keypad arrow keys etc
        self.display.cwin.keypad(True)

    def setup_default_display(self, _):
        """Default method to create a simmple demonstration
        display.
        """
        # Create a SubWindow instance for menu messages
        menuwin = SubWindow(self.display, 10, 30, 2, 2, "Menu")

        # Add some static menu items to the menu Window.
        #
        # These never change so they do not need update
        # callback functions. Note that you can also
        # use a single Textfield to display multiple
        # lines of text. Any empty, trailing newlines
        # will be stripped from your text.
        menurow = menuwin.get_first_row()
        menucol = menuwin.get_center_col()
        menu1 = (
            "Resize at will\n"
            "Ctrl-x to exit\n"
            "\n"
            "-- Could not find --\n"
            "-- demoprocess.py --\n"
            "\n"
            "Provide that module\n"
            "to see more features!"
        )
        menu1field = Textfield(menurow, menucol, Align.CENTER)
        menu1field.write(menu1)
        menuwin.add_field(menu1field)

        # The menu Window is read-only so make it unselectable
        menuwin.set_selectable(False)

    def setup_default_responses(self, _):
        """Configure the default key responses for this simple
        demonstration UI.
        """
        # Note that curses.ascii.ctrl('x') returns the same
        # type you pass to it; given 'x' it returns string
        # '\x18', not the integer value 0x18.
        #
        # ord() converts a character to its integer value.
        #
        # So to get the integer value we need to use ord()
        # on either the argument or on the return value. Either
        # way will work.
        #
        # Create a KeyResponse instance for Ctrl-x and
        # add it to the display Window.
        ctrl_x_key = KeyResponse("ctrl_x", ord(curses.ascii.ctrl("x")))
        self.display.add_key(ctrl_x_key)
        ctrl_x_key.bind(self.kr_done_with_ui)


#
# The code below runs only when cursesui.py is invoked from the command
# line with "python3 cursesui.py"
#
if __name__ == "__main__":
    # The normal curses keyboard handling system adds a
    # configurable delay to the ESCAPE key so that it can
    # be combined with other keys to generate special keycodes.
    # The delay is typically around 1 second, which can be
    # noticably slow if you are not using the ESCAPE key that way.
    # You can change the delay by setting the ESCDELAY environment
    # variable to a shorter delay but you have to change it before
    # the curses windowing system gets initialized.
    #
    # Since the demoUI system does use the ESCAPE key we will set
    # a shorter delay (in milliseconds) here.
    import os

    os.environ.setdefault("ESCDELAY", "25")

    # Try to set up a simple demonstration process to run
    # concurrently with the CursesUI instance.
    try:
        from demoprocess import DemoProcess

        demo_process = DemoProcess()

        # Create the demonstration user interface, telling it how
        # to set up the display and keyboard responses.
        demoUI = CursesUI(
            demo_process.setup_demo_display,
            demo_process.setup_demo_responses,
            "CursesUI Full Demo",
        )

        # Alternatively you can install the display and key response
        # setup routines after creating the CursesUI instance, like
        # so:
        #
        # demoUI = CursesUI()
        # demoUI.set_display_builder(demo_process.setup_demo_display)
        # demoUI.set_response_builder(demo_process.setup_demo_responses)

        # Tell the user interface to run some demo processes concurrently.
        demoUI.add_coroutine(demo_process.run_fast)
        demoUI.add_coroutine(demo_process.run_slow)

    # Import of demoprocess failed. So just run a very simple
    # demonstration without a concurrent process.
    except ImportError:
        demoUI = CursesUI()
        demoUI.add_title("CursesUI Basic Demo")

    # Set up the logging level for this demonstration.
    #
    # Typical log filter levels are logging.DEBUG
    # for development, logging.ERROR for normal use.
    # Set level to logging.CRITICAL + 1 to suppress
    # all log messages from a CursesUI instance.
    #
    # demoUI.initialize_loglevel(logging.DEBUG)
    demoUI.initialize_loglevel(logging.WARNING)

    # Run the CursesUI instance until the user quits
    demoUI.run()
