#include "FreeImage.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <list>


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
		if(fif != FIF_UNKNOWN) {
			// check that the plugin has sufficient writing and export capabilities ...
	//		WORD bpp = FreeImage_GetBPP(dib);
		//	if(FreeImage_FIFSupportsWriting(fif) && FreeImage_FIFSupportsExportBPP(fif, bpp)) {
				// ok, we can save the file
				bSuccess = FreeImage_Save(fif, dib, lpszPathName, flag);
				// unless an abnormal bug, we are done !
		//	}
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

public:
	bool addImgFile(const char* pathName, int flag = 0)  {
		FIBITMAP *img = GenericLoader(pathName, flag);
		if (img == NULL) 
			return false;
		chunks.push_back(img);
		return true;
	};

	virtual FIBITMAP* finalize(bool showProgress = false) = 0;

	bool finalizeAndSave(const char* outputPath) {
		printf("finalize & safe %s\n", outputPath);
		FIBITMAP *img = finalize();
		return 	GenericWriter(img, outputPath, 0);
	}


};

class PbrtTaskCollector: public TaskCollector {

private:
	int darkest;
	int lightest;

public:
	PbrtTaskCollector() : darkest(NULL), lightest(NULL) {};
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

		FIBITMAP *finalImage = FreeImage_Copy(*it, 0, height, width, 0);
	


		for (it++; it != chunks.end(); it++) {
				for(unsigned int y = 0 ; y < height ; y++) {
					FIRGBAF *srcbits = (FIRGBAF *) FreeImage_GetScanLine(*it, y);
					FIRGBAF *dstbits = (FIRGBAF *) FreeImage_GetScanLine(finalImage, y);
					for(unsigned int x = 0 ; x < width  ; x++) {
						dstbits[x].red += srcbits[x].red;
						dstbits[x].blue += srcbits[x].blue;
						dstbits[x].green += srcbits[x].green;
					}
				}
		}

	/*	unsigned int numParts = chunks.size();
		unsigned int chunkHeight = 12;
		unsigned int chunkWidth = 427;

		unsigned int lastHeight = height -1 - chunkHeight;
		unsigned int lastWidth = chunkWidth;
		unsigned int restWidth = chunkWidth;
		for (it++; it != chunks.end(); it++) {
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


class MentalRayTaskCollector: public TaskCollector {

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

	if (strcmp(argv[1], "pbrt") == 0) {
		taskCollector = &(PbrtTaskCollector());
	} else if (strcmp(argv[1], "mr") == 0) {
		taskCollector = &(MentalRayTaskCollector());
	} else {
		printf("Possible types: 'mr', 'pbrt'\n");
		return -1;
	}


	for (int i = 3; i < argc; i++) {
		if (! taskCollector->addImgFile(argv[i])) {
			printf("Can't add file: %s\n", argv[i]);
		}
	}
	/*char text[14];
	sprintf_s(text, (size_t) 14, "temp0000%d.exr", 1);
	printf("%s\n", text);
	for (int i = 0; i < 10; i++) {
		sprintf_s(text, 14, "temp0000%d.exr", i);
		printf("%s\n", text);
		if (! pbrtTC.addImgFile(text)) {
			printf("appendTask error %s\n", text);
		}
	}
	for (int i = 10; i < 60; i++) {
		sprintf_s(text, 14, "temp000%d.exr", i);
		printf("%s\n", text);
		if (! pbrtTC.addImgFile(text)) {
			printf("appendTask error %s\n", text);
		}
	}
	*/

	FIBITMAP *finalImage = taskCollector->finalize();
	taskCollector->finalizeAndSave(argv[2]); 

	
	// call this ONLY when linking with FreeImage as a static library
#ifdef FREEIMAGE_LIB
	FreeImage_DeInitialise();
#endif // FREEIMAGE_LIB

	return 0;
}