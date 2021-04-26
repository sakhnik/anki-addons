#!/bin/bash -e

this_dir=$(readlink -f .)

ln -sf "$this_dir/copy_solia" ~/.local/share/Anki2/addons21/
