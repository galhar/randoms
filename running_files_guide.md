# A guide for editing the code
1. dont change any rows that are not related to the current change you were asked to do. DO NOT.
2. do not remove comments that are not comments on the specific rows of the code you were asked to change their logic. DO NOT.
3. Make sure while you implement the code you thoroughly go over the references used, and stick as close to their implementations as possible.
4. build code that is as close as possible to the references, as clean as possible, and as sturctured as possible so that each rows chunck you write has its own purpose.

# A guide for running the code

You must actiavte general conda environment to run the code.
And then in a seperate command run the code.

So do :
```
conda activate general
<command to run the code>
```

When running the code, it takes a few minutes to work. So DO NOT USE KEYBOARD INTERUPT. Be patient. Wait for the code to finish at least 3 minutes before you interrupt it.
In order to know it is not stuck, add a line as the first line of the script you are running:
```
print("Script starting...") # Helping cursorai to not keyboard interrupt when running it
```



# Debugging
In order to debug, you are expected to write the code, run it, see the errors, fix them, re-run it, and so on. Keep running and fixing until no errors happen. 
When deubgging, you can insert prints as you need. In which case, dont forget to remove them after you use these prints.

# Cleanup
After finished successfully, before you finish your job, remove the unncessary prints and exception catches. After removing, re-run to see it still works. 
Only remove prints and exception catches you added. As written before, dont remove any comment or print or code line that was there before you and isn't requried to be changed for the core functionality.


