# Customisation of GatherUp

GatherUp can easily be run without installing configuration files (in which case it uses default settings from within the package).

However it is also possible to run the `--setup` option to add the configuration files and then customise those so that they list projects of interest to you, with your most used ones first (or any order you prefer).

The configuration file location will be platform specific (thanks to [Confuse](https://github.com/beetbox/confuse) which handles all that). You will see it displayed when you run setup. On Windows it will likely be beneath the AppData folder in your user directory, eg something like **C:\\Users\\username\\AppData\\Roaming\\gatherup\\**.  On Linux it will likely be in **~/.config/gatherup/**.


## config.yaml

This is the main configuration file and is in the root of the gatherup configuration directory.

You can set the key files to be in customised locations, but by default they reside in other directories within the configuration directory.

**CONFIG FILE FORMAT IS EXPECTED TO CHANGE SOMEWHAT DURING INITIAL DEVELOPMENT**

## project_details.txt

This contains the details for commonly accessed projects and the URL(s) where gatherup content may likely be posted.

Additional settings are present in the file but not yet used.


## Example files

It seems unlikely that typical users will want to edit the example files but this is possible.

## Broader customisation

This software is open source so if you have a particular need that is not likely to be included in the main project, you should be able to adapt the code to change how it gathers details and what details it gathers.  This would mean that you need to reintegrate code if you wish to stay current.  In the future, depending on uptake, I may explore whether there's a clean way to offer extendibility.

However, bear in mind that the payoff on effort spent customising would typically need to be reasonably big before it became worth it. You could easily spend more time than it would take to do minor adjustments by hand!
