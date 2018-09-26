#!/bin/bash
# This allows from inside script output redirection
# Golem by default filters files ending with .log
# Thats why output has .txt extension
{
    mkdir -p $OUTPUT_DIR/raspa
    cp $RESOURCES_DIR/simulation.input $OUTPUT_DIR/raspa/simulation.input

    # Copy input files to appropriate raspa/share directories
    cd $RESOURCES_DIR/data
    tar xf CCXL_largepore_crystal.tar.gz
    cp -r CCXL_largepore_crystal/* $RASPA_DIR/share/raspa/structures/cif
    cp -r share/ $RASPA_DIR

    cd $OUTPUT_DIR/raspa
    $RASPA_DIR/bin/simulate
    rm $OUTPUT_DIR/raspa/simulation.input
} > $OUTPUT_DIR/stdout.txt 2>$OUTPUT_DIR/stderr.txt
