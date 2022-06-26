"""
VPA - VGDL Permutation Algorithm (for each prompt):

1) Read in a .txt file containing a VGDL block
2) Permute ordering of SpriteSet, LevelMapping, InteractionSet and TerminationSet
3) For the SpriteSet (children always belong to original parent):
    a) permute the lines
    b) add "avatar" if none exists
    c) add "wall" if none exists
    d) prepend each line with its number - e.g. "1) "
    e) prepend each subsequent indented row with a "c"*
4) For the LevelMapping:
    a) permute the lines
    b) add "A" if none exists
    c) add "w" if none exists
5) For the InteractionSet:
    a) permute the line
    b) within each line:
        i) permute the order of the sprites in the line (e.g. "movable wall  > stepBack" -> "wall movable  > stepBack")
    c) prepend each line with its number - e.g. "1) "
6) For the TerminationSet:
    a) permute the lines
    b) prepend each line with its number - e.g. "1) "



PPA - Prompt Permutation Algorithm (for this example assume 5 characteristics):

1) For each game (append "vgdlgame") - remove permutation:
    a) Permute the prompt consisting of all 5 traits (a trait example would be "7 sprites")
    b) Permute the prompt consisting of all 4 traits
    c) Permute the prompt consisting of all 3 traits
    d) Permute the prompt consisting of all 2 traits
    e) Permute the prompt consisting of all 1 traits
    f) empty prompt



Meta Training Data Generation Algorithm (for this example assume we read in zelda):

    1) Read in a normalized vgdl block from a zelda.txt file (from vgdl_src directory)
    2) Look up the traits_dict using key=zelda to get the prompts
    3) Run PPA and for each permutation:
        a) Run VPA and for each permutation:
            i) write the (prompt, vgdl block) to ~gpt-2/src/data directory with the filename as zelda_<#>.txt

==========
EXAMPLE - prompt: 4 sprites
=========

BasicGame
  SpriteSet
    1) sprite1 > Immovable color=BLUE
    2) sprite2 > physicstype=GridPhysics
    3)     csprite1 > MovingAvatar
    4)     csprite2 > RandomNPC speed=0.6
  TerminationSet
    1) SpriteCounter stype=butterfly win=True
    2) SpriteCounter stype=cocoon win=False
  InteractionSet
    1) butterfly avatar > killSprite
    2) butterfly cocoon > cloneSprite
    3)cocoon butterfly > killSprite
    4) animal wall > stepBack
  LevelMapping
    1 > butterfly
    0 > cocoon
"""

import os
import re
import itertools
import random
import argparse

from traits_dict import TRAITS_DICT


VGDL_SRC_DIR = "data/vgdl_src/{}"
TRAINING_TXTS_DIR = "data/training_txts/{}"


def is_header(vgdl_line):
    return re.search(r'[a-z]', vgdl_line, re.I) == 2


def get_permutations_lst(vgdl_src_block, start_term, end_term):
    if len(end_term) > 0:
        start_idx, end_idx = vgdl_src_block.index(start_term), vgdl_src_block.index(end_term)
    else:
        start_idx, end_idx = vgdl_src_block.index(start_term), len(vgdl_src_block)
    src_lst = vgdl_src_block[start_idx+1: end_idx]
    permutations_lst = list(itertools.permutations(src_lst))
    for permutations_idx in range(len(permutations_lst)):
        permutations_lst[permutations_idx] = list(permutations_lst[permutations_idx])
        permutations_lst[permutations_idx].insert(0, start_term)
    return permutations_lst


def preappend_enum(permuation_list):
    """
     Prepends the enum e.g. 1) , 2) to beginning of each row in a vgdl block component
    """
    idx = 0
    for i in range(len(permuation_list)):
        if idx == 0:
            pass
        else:
            permuation_list[i] = f"{idx})" + permuation_list[i]
        idx += 1
    return permuation_list


def preappend_spriteset(sprite_permuation_lst):
    new_permutation_lst = []

    # First unravel any hierarchy
    for i in range(len(sprite_permuation_lst)):
        spriteset_row = sprite_permuation_lst[i]
        if 'csprite' not in spriteset_row:
            new_permutation_lst.append(sprite_permuation_lst[i])
        else:
            # Find all csprite matches and add to positions list
            positions = []
            for m in re.finditer(r"c+sprite\d", spriteset_row):
                # print(f"pos: ({int(m.start())}, {int(m.end())}): {spriteset_row[int(m.start()): int(m.end())]}")
                positions.append((int(m.start()), int(m.end())))
                print(f"{spriteset_row[int(m.start()): int(m.end())]} in {spriteset_row[:]}")

            # First sprite in row is the parent (i.e. doesn'r start with a c
            first_end = positions[0][1]
            positions.insert(0, (0, first_end))
            for pos_idx in range(0,len(positions)-1):
                # get entire row
                new_row = spriteset_row[positions[pos_idx][0]:positions[pos_idx+1][0]]
                # get only the c*sprite token at the position e.g.: "pos: (51, 60): ccsprite1"
                num_spaces_in_child_row = spriteset_row[positions[pos_idx][0]:positions[pos_idx][1]].count("c")
                # check if child sprite or the starting parent row
                if 'csprite' in new_row and new_row[0] == "c":
                    new_child_row = "    " + (" " * int(num_spaces_in_child_row)*2) + new_row + "\n"
                else:
                    new_child_row = new_row + "\n"
                new_permutation_lst.append(new_child_row)

            # Since above loop doesn't cover last element check it here
            final_subrow = spriteset_row[positions[-1][0]:]
            # spriteset_row[positions[-1][0]:positions[-1][1]] keys in matches token like "ccsprite2" in new row
            num_spaces_in_child_row = spriteset_row[positions[-1][0]:positions[-1][1]].count("c")
            new_child_row = "    " + (" " * int(num_spaces_in_child_row)*2) + final_subrow
            new_permutation_lst.append(new_child_row)

    # then enum
    idx = 0
    for i in range(len(new_permutation_lst)):
        if idx == 0:
            pass
        else:
            new_permutation_lst[i] = f"{idx})" + new_permutation_lst[i]
        idx += 1
    return new_permutation_lst


def get_set_nums(vgdl_src_block, start_term, end_term):
    """
     Function to get the number of rows in a either SpriteSet, InteractionSet, TerminationSet, or LevelMapping
    """
    if len(end_term) > 0:
        start_idx, end_idx = vgdl_src_block.index(start_term), vgdl_src_block.index(end_term)
    else:
        start_idx, end_idx = vgdl_src_block.index(start_term), len(vgdl_src_block)
    return end_idx - start_idx - 1


def get_vgdl_component_lst(vgdl_src_block, start_term, end_term):
    if len(end_term) > 0:
        start_idx, end_idx = vgdl_src_block.index(start_term), vgdl_src_block.index(end_term)
    else:
        start_idx, end_idx = vgdl_src_block.index(start_term), len(vgdl_src_block)
    src_lst = vgdl_src_block[start_idx: end_idx]
    idx = 0
    for i in range(len(src_lst)):
        if idx == 0:
            pass
        else:
            src_lst[i] = f"{idx})" + src_lst[i]
        idx += 1

    return src_lst


def concat_vgdl_components(vgdl_components_lst):
    # Decide whether to shuft the component order
    shuffle_order = random.uniform(0, 1) > 0.25
    if shuffle_order:
        random.shuffle(vgdl_components_lst)

    vgdl_lst = ['BasicGame\n']
    for component_lst in vgdl_components_lst:
        for line in component_lst:
            vgdl_lst.append(line)

    return ''.join(vgdl_lst)

# TODO: Add argparser and main method to file
# TODO: Add arguments to argparser: a) debug flag, b) cutoffs for max num of permutations for each component of vgdl block (to be inserted into current index slicing under comment # Prepend each component with enumeration)
# def main():
#     args = argparse.ArgumentParser()


for game_name, game_prompts_lst in TRAITS_DICT.items():
    game_combo_dict = {game_name: []}
    game_file = f"{game_name}.txt"
    vgdl_src_path = VGDL_SRC_DIR.format(game_file)
    print(f"Reading in vgdl source from file {vgdl_src_path}\n")

    vgdl_src_block = None
    # Read in normalized vgdl source block
    with open(vgdl_src_path, "r") as f:
        vgdl_src_block = f.readlines()


    # Get the permutations for each of the 4 vgdl components
    spriteset_permutations_lst = get_permutations_lst(vgdl_src_block, '  SpriteSet\n', '  LevelMapping\n')
    random.shuffle(spriteset_permutations_lst)
    levelmapping_permutations_lst = get_permutations_lst(vgdl_src_block, '  LevelMapping\n', '  InteractionSet\n')
    random.shuffle(levelmapping_permutations_lst)
    interactionset_permutations_lst = get_permutations_lst(vgdl_src_block, '  InteractionSet\n', '  TerminationSet\n')
    random.shuffle(interactionset_permutations_lst)
    terminationset_permutations_lst = get_permutations_lst(vgdl_src_block, '  TerminationSet\n', '')
    random.shuffle(terminationset_permutations_lst)


    # Prepend each component with enumeration
    print(f"game {game_name} spriteset_permutations_lst\n {len(spriteset_permutations_lst)}")
    spriteset_permutations_lst = [preappend_spriteset(s) for s in spriteset_permutations_lst[:5]]

    levelmapping_permutations_lst = [preappend_enum(l) for l in levelmapping_permutations_lst[:10]]
    interactionset_permutations_lst = [preappend_enum(i) for i in interactionset_permutations_lst[:10]]
    terminationset_permutations_lst = [preappend_enum(t) for t in terminationset_permutations_lst[:2]]

    # get all combinations via selecting one permutation from each set at a time
    vgld_combinations_list = [spriteset_permutations_lst, levelmapping_permutations_lst, interactionset_permutations_lst, terminationset_permutations_lst]
    vgdl_combinations = [concat_vgdl_components(list(v)) for v in itertools.product(*vgld_combinations_list)]

    # Create the permutations for the game prompts
    all_combos_game_prompts_lst = []
    for r in range(len(game_prompts_lst)):
        all_combos_game_prompts_lst.extend(itertools.permutations(game_prompts_lst, r+1))

    all_combos_game_prompts_lst = [' '.join(p) + " vgdlgame.\n" for p in all_combos_game_prompts_lst]
    random.shuffle(all_combos_game_prompts_lst)

    prompt_vgdl_combo_pairs = [all_combos_game_prompts_lst, vgdl_combinations]
    prompt_vgdl_combo_pairs = [list(c) for c in itertools.product(*prompt_vgdl_combo_pairs)]

    vgdl_block_num = 1
    for pair in prompt_vgdl_combo_pairs[:3]:
        file_path = TRAINING_TXTS_DIR.format(f"{game_name}_{vgdl_block_num}.txt")
        with open(file_path, "w") as f:
            f.writelines(pair)
        vgdl_block_num += 1






