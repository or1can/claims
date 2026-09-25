# Widget

Check the installed version:

<!-- verify: ./widget --version -->
```
widget 2.1.0
```

Count the plugins that are switched on:

<!-- verify: ./widget plugins | grep -c enabled -->
```
3
```

Print the resolved configuration:

<!-- verify: ./widget config -->
The block that should follow this marker was lost in an edit, so the
marker has nothing to pin.

Print what is running:

<!-- verify: ./widget status -->
```
widget 2.1.0, 3 plugins enabled
```
