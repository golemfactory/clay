#include "FreeImage.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <list>
#include <queue>
#include <iostream>


std::queue<FIBITMAP *> alphaChunks;	

/** Generic image loader
	@param lpszPathName Pointer to the full file name
	@param flag Optional load flag constant
	@return Returns the loaded dib if successful, returns NULL otherwise
*/
FIBITMAP* GenericLoader(const char* lpszPathName, int flag) {
	FREE_IMAGE_FORMAT fif = FIF_UNKNOWN;

	// check the file signature and deduce its format
	// (the second argument is currently not used by FreeImage)
	fif = FreeImage_GetFileType(lpszPathName, 0);
	if(fif == FIF_UNKNOWN) {
		// no signature ?
		// try to guess the file format from the file extension
		fif = FreeImage_GetFIFFromFilename(lpszPathName);
	}
	// check that the plugin has reading capabilities ...
	if((fif != FIF_UNKNOWN) && FreeImage_FIFSupportsReading(fif)) {
		// ok, let's load the file
		FIBITMAP *dib = FreeImage_Load(fif, lpszPathName, flag);
		// unless a bad file format, we are done !
		return dib;
	}
	return NULL;
}

unsigned int min(unsigned int a, unsigned int b) {
	return a < b ? a : b;
}

/** Generic image writer
	@param dib Pointer to the dib to be saved
	@param lpszPathName Pointer to the full file name
	@param flag Optional save flag constant
	@return Returns true if successful, returns false otherwise
*/
bool GenericWriter(FIBITMAP* dib, const char* lpszPathName, int flag) {
	FREE_IMAGE_FORMAT fif = FIF_UNKNOWN;
	BOOL bSuccess = FALSE;

	if(dib) {
		// try to guess the file format from the file extension
		fif = FreeImage_GetFIFFromFilename(lpszPathName);
		if(fif != FIF_UNKNOWN ) {
			// check that the plugin has sufficient writing and export capabilities ...
			if(FreeImage_FIFSupportsWriting(fif) && FreeImage_FIFSupportsExportType(fif, FreeImage_GetImageType(dib))) {
				// ok, we can save the file
				bSuccess = FreeImage_Save(fif, dib, lpszPathName, flag);
				// unless an abnormal bug, we are done !
			} else {
				printf("Can't save file\n");
			}
		}
	}
	return (bSuccess == TRUE) ? true : false;
}

// ----------------------------------------------------------

/**
	FreeImage error handler
	@param fif Format / Plugin responsible for the error 
	@param message Error message
*/
void FreeImageErrorHandler(FREE_IMAGE_FORMAT fif, const char *message) {
	printf("\n*** "); 
	if(fif != FIF_UNKNOWN) {
		printf("%s Format\n", FreeImage_GetFormatFromFIF(fif));
	}
	printf(message);
	printf(" ***\n");
}

// ----------------------------------------------------------

class TaskCollector {
	
protected:
	std::list<FIBITMAP *> chunks;
	/*std::queue<FIBITMAP *> alphaChunks; */
	

public:
	
	bool acceptTask(const char* pathName, int flag = 0)  {
		FIBITMAP *img = GenericLoader(pathName, flag);
		if (img == NULL) 
			return false;
		chunks.push_back(img);
		return true;
	};

	bool acceptAlpha( const char* pathName, int flag = 0) {
		FIBITMAP *img = GenericLoader(pathName, flag);
		if (img == NULL)
			return false;
		alphaChunks.push(img);
		return true;
	};

	virtual FIBITMAP* finalize(bool showProgress = false) = 0;

	bool finalizeAndSave(const char* outputPath) {
		printf("finalize & safe %s\n", outputPath);
		FIBITMAP *img = finalize();
		return 	GenericWriter(img, outputPath, EXR_FLOAT );
	};

};

class AddTaskCollector: public TaskCollector {

public:
	FIBITMAP* finalize(bool showProgress = false) {
		if (chunks.empty()) {
			return NULL;
		}
		if (showProgress) {
			printf("Adding all accepted chunks to the final image\n");
		}

		std::list<FIBITMAP*>::iterator it = chunks.begin();
		unsigned int width = FreeImage_GetWidth(*it);
		unsigned int height = FreeImage_GetHeight(*it);
		FREE_IMAGE_TYPE type = FreeImage_GetImageType(*it);

		FIBITMAP *finalImage = FreeImage_Copy(*it, 0, height, width, 0);

		int bytesapp = FreeImage_GetLine(*it) / FreeImage_GetWidth(*it);

		for (it++; it != chunks.end(); it++) {
			switch(type) {
				case FIT_RGBF:
					for(unsigned int y = 0 ; y < height ; y++) {
						FIRGBF *srcbits = (FIRGBF *) FreeImage_GetScanLine(*it, y);
						FIRGBF *dstbits = (FIRGBF *) FreeImage_GetScanLine(finalImage, y);
	
						for(unsigned int x = 0 ; x < width  ; x++) {
							dstbits[x].red += srcbits[x].red;
							dstbits[x].blue += srcbits[x].blue;
							dstbits[x].green += srcbits[x].green;
						}
					}
					break;

				case FIT_RGBAF:
					for(unsigned int y = 0 ; y < height ; y++) {
						FIRGBAF *srcbits = (FIRGBAF *) FreeImage_GetScanLine(*it, y);
						FIRGBAF *dstbits = (FIRGBAF *) FreeImage_GetScanLine(finalImage, y);
	
						for(unsigned int x = 0 ; x < width  ; x++) {
							dstbits[x].red += srcbits[x].red;
							dstbits[x].blue += srcbits[x].blue;
							dstbits[x].green += srcbits[x].green;
							dstbits[x].alpha += srcbits[x].alpha;
						}
					}
					break;
				
			}
		}

		while( !alphaChunks.empty() ) {
			for(unsigned int y = 0 ; y < height ; y++) {
				FIRGBAF *srcbits = (FIRGBAF *) FreeImage_GetScanLine(alphaChunks.front(), y);
				FIRGBAF *dstbits = (FIRGBAF *) FreeImage_GetScanLine(finalImage, y);
	
				for(unsigned int x = 0 ; x < width  ; x++) {
					dstbits[x].alpha += srcbits[x].red + srcbits[x].blue + srcbits[x].green;
				}
			}
			alphaChunks.pop();
		}

	/*	unsigned int numParts = chunks.size();
		unsigned int chunkHeight = 12;
		unsigned int chunkWidth = 427;

		unsigned int lastHeight = height -1 - chunkHeight;
		unsigned int lastWidth = chunkWidth;
		unsigned int restWidth = chunkWidth;
		for ( it++; it != chunks.end(); it++) { 
			printf("lastHeight = %d, lastWidth = %d restWidth = %d\n", lastHeight, lastWidth, restWidth);
			bool continueChunk = true;
			while (continueChunk) {
				printf("lastHeight = %d, lastWidth = %d restWidth = %d\n", lastHeight, lastWidth, restWidth);
				continueChunk = false;
				for(unsigned int y = lastHeight ; y < min(height, lastHeight + chunkHeight + 1) ; y++) {
					FIRGBAF *srcbits = (FIRGBAF *) FreeImage_GetScanLine(*it, y);
					FIRGBAF *dstbits = (FIRGBAF *) FreeImage_GetScanLine(finalImage, y);
					for(unsigned int x = lastWidth ; x < min(width, lastWidth + restWidth)  ; x++) {
						//printf("y = %d x= %d\n", y, x);
						dstbits[x].red = srcbits[x].red;	
						dstbits[x].green = srcbits[x].green;
						dstbits[x].blue = srcbits[x].blue;	
					}
				}
				if (width < lastWidth + restWidth) {
						continueChunk = true;
						lastHeight -= chunkHeight - 1;
						restWidth -= width - lastWidth;
						lastWidth = 0;
				} else {
						lastWidth += restWidth;
						restWidth = chunkWidth;
				}
			}
		}*/

		
		return finalImage;
	}
};


class PasteTaskCollector: public TaskCollector {

public:

	FIBITMAP* finalize(bool showProgress = true) {
		if (chunks.empty()) {
			return NULL;
		}
		if (showProgress) {
			printf("Adding all accepted chunks to the final image\n");
		}
		std::list<FIBITMAP*>::iterator it = chunks.begin();
		unsigned int width = FreeImage_GetWidth(*it);		
		unsigned int chunkHeight = FreeImage_GetHeight(*it);
		unsigned int height =  chunkHeight * chunks.size() ;
		unsigned int currentHeight = height - chunkHeight;

		FREE_IMAGE_TYPE type = FreeImage_GetImageType(*it);
		int bpp = FreeImage_GetBPP(*it);
		FIBITMAP *finalImage = FreeImage_AllocateT(type, width, height, bpp);

		for (; it != chunks.end(); it++) {
			switch(type) {
				case FIT_RGBF:
					for(unsigned int y = 0 ; y < chunkHeight ; y++) {
						FIRGBF *srcbits = (FIRGBF *) FreeImage_GetScanLine(*it, y);
						FIRGBF *dstbits = (FIRGBF *) FreeImage_GetScanLine(finalImage, y + currentHeight);
						for(unsigned int x = 0 ; x < width  ; x++) {				
							dstbits[x].red = srcbits[x].red;
							dstbits[x].blue = srcbits[x].blue;
							dstbits[x].green = srcbits[x].green;
						}
					}
					break;
				case FIT_RGBAF:
					for(unsigned int y = 0 ; y < chunkHeight ; y++) {
						FIRGBAF *srcbits = (FIRGBAF *) FreeImage_GetScanLine(*it, y);
						FIRGBAF *dstbits = (FIRGBAF *) FreeImage_GetScanLine(finalImage, y + currentHeight);
						for(unsigned int x = 0 ; x < width  ; x++) {				
							dstbits[x].red = srcbits[x].red;
							dstbits[x].blue = srcbits[x].blue;
							dstbits[x].green = srcbits[x].green;
							dstbits[x].alpha = srcbits[x].alpha;
						}
					}
					break;
			}
			currentHeight -= chunkHeight;
		}
		
		return finalImage;
	}

};


int 
main(int argc, char *argv[]) {
	
	// call this ONLY when linking with FreeImage as a static library
#ifdef FREEIMAGE_LIB
	FreeImage_Initialise();
#endif // FREEIMAGE_LIB

	// initialize your own FreeImage error handler

	FreeImage_SetOutputMessage(FreeImageErrorHandler);

	// print version & copyright infos

	printf("FreeImage version : %s", FreeImage_GetVersion());
	printf("\n");
	printf(FreeImage_GetCopyrightMessage());
	printf("\n");

	

	if (argc < 4)  {
		printf("Usage: taskcollector.exe <type> <outputfile> <inputfile1> [<input file2> ...]\n");
		return -1;
	}

	TaskCollector *taskCollector;

	if (strcmp(argv[1], "add") == 0) {
		taskCollector = new AddTaskCollector();
	} else if ( strcmp( argv[1], "paste") == 0) {
		taskCollector = new PasteTaskCollector();
	} else {
		printf("Possible types: 'add', 'paste'\n");
		return -1;
	}


	for (int i = 3; i < argc; i++) {
		if (strstr(argv[i], "Alpha") != NULL) {
			if (! taskCollector->acceptAlpha(argv[i]) ) {
				printf ("Can't add file: %s\n", argv[i]);
			}
		} else {
			if (! taskCollector->acceptTask(argv[i]) ) {
				printf("Can't add file: %s\n", argv[i]);
			}
		}
	}

//	FIBITMAP *finalImage = taskCollector->finalize();
	//taskCollector->alphaQueue();
	taskCollector->finalizeAndSave(argv[2]); 

	
	// call this ONLY when linking with FreeImage as a static library
#ifdef FREEIMAGE_LIB
	FreeImage_DeInitialise();
#endif // FREEIMAGE_LIB

	return 0;
}