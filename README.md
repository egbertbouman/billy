# Billy

Billy is a playlist builder offering a new interface to the Jamendo dataset, including explicit search, automatic recommendation and playlist organization and playback functionality.


**This README reflects the README we submitted with the MIREX GC15UX entry submission for Billy.**


* If you want to work with Billy as a user, please find instructions below.
* If you want to contribute to Billy, feel free to fork this project. We apologize in advance for not having extensive documentation ready yet for developers, but feel free to reach out to us with any questions you may have.


# Quickstart

Just go to http://musesync.ewi.tudelft.nl/billy , set up your first playlist, and start building your playlists right away!

- Use the search field on top of the page to search for songs in the Jamendo dataset.
- Beyond search results, we offer automatic recommendations from the dataset. These will continuously adapt to the playlist you currently are building.
- Hit 'Create new' to make a new playlist.
- Hit 'Delete current' to remove the currently active playlist.
- Hit 'Export JSON' to export all your playlists to a JSON file you can store on your computer.
- Hit 'Import JSON' to import playlists from a locally stored JSON file back into Billy.

# Technical requirements

Billy is responsive, so you can access and use it at your favorite window size. However, we should mention that Billy is intended for desktop usage, so the experience is at your own risk if you access the site on smaller mobile devices. :)

As for browsers: we mostly developed and tested Billy using Google Chrome, and can definitely recommend this browser - however, Billy should work with any up to date browser with cookies and Javascript enabled.

# How is my data stored?

We do not store any data that can be traced to individual users, and for ease of instant use, we also do not work with user profile management at this stage. We also won't share playlists you created with other users in the current Billy release (if we may wish to do it in a later release, we will ask your explicit permission).

We will try to store your playlist state as a cookie, so you can resume with an existing collection when revisiting Billy from the same browser, if the browser does not auto-remove cookies after a session. Alternatively, you can export and import dumps of your playlists through the Import/Export functionality.

# Can you tell a bit more about the concept underlying Billy?

The founding thought underlying Billy is that playlists will be created with a certain intent in mind (e.g. to support daily activities, to have listeners enter a specific affective state, or to group songs with similar style). Relevant dimensions contributing to song suitability for a playlist will depend on this, as will be the question what will be most central to the ultimate holistic playlist consumption experience: the music, or the use context it is intended for. Next to this, we also believe that song search interfaces should not necessarily be limited to specific pre-defined categories of music labels (e.g. mood or genre only), both in terms of vocabulary for query formulation, as well as underlying search mechanisms.

The 2015 edition of the MIREX GCUX is planned to take place in two rounds, and we would like to take advantage of this by separating 'holistic system experience' from 'holistic playlist consumption experience', also noting that published assessment criteria especially target the first of these aspects. In our current submission, we therefore aimed to make Billy as clean and basic as possible in both functionality and presentation. In future submissions, we plan to integrate more sophisticated analysis and organization mechanisms, of which the impact can be assessed against a baseline which will be set by the current release.